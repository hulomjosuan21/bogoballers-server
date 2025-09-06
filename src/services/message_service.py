from collections import defaultdict
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload
from src.models.user import UserModel
from src.models.message import MessageModel
from src.extensions import AsyncSession, sio
from src.utils.api_response import ApiException

class MessageService:
    async def get_conversations(self, user_id: str):
        async with AsyncSession() as session:
            result = await session.execute(
                select(MessageModel)
                .where(
                    or_(
                        MessageModel.sender_id == user_id,
                        MessageModel.receiver_id == user_id,
                    )
                )
                .options(
                    selectinload(MessageModel.sender),
                    selectinload(MessageModel.receiver),
                )
                .order_by(MessageModel.sent_at.asc())
            )
            messages = result.scalars().all()

            conversations = defaultdict(list)

            for msg in messages:
                if msg.sender_id == user_id:
                    other_id = msg.receiver_entity_id
                    other_name = msg.receiver_name
                    other_user_id = msg.receiver_id
                else:
                    other_id = msg.sender_entity_id
                    other_name = msg.sender_name
                    other_user_id = msg.sender_id

                conversations[other_id].append({
                    "message": msg.to_json_message_only(),
                    "user_id": other_user_id,
                    "entity_id": other_id,
                    "name": other_name,
                })

            response = []
            for _, msgs in conversations.items():
                meta = msgs[0]
                response.append({
                    "conversation_with": {
                        "user_id": meta["user_id"],
                        "entity_id": meta["entity_id"],
                        "name": meta["name"],
                    },
                    "messages": [m["message"] for m in msgs]
                })

            return response
    
    async def send_message_notification(self, data: dict, enable_notification: bool) -> str:
        async with AsyncSession() as session:
            try:
                sender_result = await session.execute(
                    select(UserModel)
                    .where(UserModel.user_id == data.get('sender_id'))
                    .options(
                        selectinload(UserModel.league_administrator),
                        selectinload(UserModel.player)
                    )
                )
                sender = sender_result.scalar_one()

                receiver_result = await session.execute(
                    select(UserModel)
                    .where(UserModel.user_id == data.get('receiver_id'))
                    .options(
                        selectinload(UserModel.league_administrator),
                        selectinload(UserModel.player)
                    )
                )
                receiver = receiver_result.scalar_one()
                
                def resolve_entity(user: UserModel) -> dict:
                    if user.league_administrator:
                        return {
                            "entity_id": user.league_administrator.league_administrator_id,
                            "entity_name": user.league_administrator.organization_name,
                        }
                    elif user.player:
                        return {
                            "entity_id": user.player.player_id,
                            "entity_name": user.player.full_name,
                        }
                    else:
                        return {
                            "entity_id": user.user_id,
                            "entity_name": user.display_name or user.email,
                        }

                sender_entity = resolve_entity(sender)
                receiver_entity = resolve_entity(receiver)

                # normalize keys expected by MessageModel
                data["sender_name"] = sender_entity.get('entity_name')
                data["sender_entity_id"] = sender_entity.get('entity_id')
                data["receiver_name"] = receiver_entity.get('entity_name')
                data["receiver_entity_id"] = receiver_entity.get('entity_id')

                msg = MessageModel(**data)
                session.add(msg)
                await session.commit()

                # refresh relations for to_json usage
                await session.refresh(
                    msg,
                    attribute_names=["sender", "receiver"]
                )

                # FCM / push notification (existing)
                await msg.send_notification(enable=enable_notification)

                # --- SOCKET.IO realtime emit ---
                # payload to send to clients
                payload = {
                    "type": "new_message",
                    "message": msg.to_json(),  # includes sender/receiver objects (to_json)
                }

                # define receiver & sender rooms (convention)
                receiver_room = f"user:{receiver.user_id}"
                sender_room = f"user:{sender.user_id}"
                # also support entity-room (conversation with entity id)
                conv_room_receiver = f"entity:{msg.receiver_entity_id}"
                conv_room_sender = f"entity:{msg.sender_entity_id}"

                # Emit asynchronously; depending on your socket server this may be a coroutine
                try:
                    # emit to receiver only
                    await sio.emit("new_message", payload, room=receiver_room, namespace="/")
                    # optionally also emit to sender (so sender's client sees message confirmed)
                    await sio.emit("new_message", payload, room=sender_room, namespace="/")
                    # also emit to entity rooms (useful if clients join entity rooms)
                    await sio.emit("conversation_update", payload, room=conv_room_receiver, namespace="/")
                    await sio.emit("conversation_update", payload, room=conv_room_sender, namespace="/")
                except Exception:
                    # don't crash the whole request if socket emit fails; log but continue
                    import traceback
                    traceback.print_exc()

                return "Message sent successfully."

            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e