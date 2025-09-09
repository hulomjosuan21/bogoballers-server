from collections import defaultdict
import time
import socketio
from sqlalchemy import or_, select, desc
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload
from src.models.user import UserModel
from src.models.message import MessageModel
from src.extensions import AsyncSession
from src.utils.api_response import ApiException
import traceback

class MessageService:
    def __init__(self):
        self._sio = None
    
    def _get_sio(self):
        if self._sio is None:
            from src.extensions import socket_service
            self._sio = socket_service.sio
        return self._sio

    async def get_conversations(self, user_id: str):
        async with AsyncSession() as session:
            try:
                result = await session.execute(
                    select(MessageModel)
                    .where(
                        or_(
                            MessageModel.sender_id == user_id,
                            MessageModel.receiver_id == user_id,
                        )
                    )
                    .options(
                        selectinload(MessageModel.sender).selectinload(UserModel.player),
                        selectinload(MessageModel.sender).selectinload(UserModel.league_administrator),
                        selectinload(MessageModel.receiver).selectinload(UserModel.player),
                        selectinload(MessageModel.receiver).selectinload(UserModel.league_administrator),
                    )
                    .order_by(MessageModel.sent_at.asc())
                )
                messages = result.scalars().all()
                conversations = defaultdict(list)

                def resolve_image(user: UserModel) -> str | None:
                    if user.league_administrator:
                        return user.league_administrator.organization_logo_url
                    elif user.player:
                        return user.player.profile_image_url
                    return None

                for msg in messages:
                    try:
                        if msg.sender_id == user_id:
                            other_user = msg.receiver
                            other_id = msg.receiver_entity_id
                            other_name = msg.receiver_name
                            other_user_id = msg.receiver_id
                        else:
                            other_user = msg.sender
                            other_id = msg.sender_entity_id
                            other_name = msg.sender_name
                            other_user_id = msg.sender_id

                        conversation_key = other_user_id
                        image_url = resolve_image(other_user)

                        conversations[conversation_key].append({
                            "message": msg.to_json(),
                            "user_id": other_user_id,
                            "entity_id": other_id,
                            "name": other_name,
                            "image_url": image_url,
                        })
                    except Exception:
                        continue

                response = []
                for conversation_key, msgs in conversations.items():
                    if not msgs:
                        continue

                    try:
                        meta = msgs[0]
                        messages_data = [m["message"] for m in msgs]
                        messages_data.sort(key=lambda x: x.get('sent_at', ''))

                        conversation = {
                            "conversation_with": {
                                "user_id": meta["user_id"],
                                "entity_id": meta["entity_id"],
                                "name": meta["name"],
                                "image_url": meta["image_url"],
                            },
                            "messages": messages_data,
                            "last_message_at": messages_data[-1].get('sent_at') if messages_data else None,
                        }

                        response.append(conversation)
                    except Exception:
                        continue

                response.sort(
                    key=lambda x: x.get('last_message_at', ''),
                    reverse=True
                )

                for conv in response:
                    conv.pop('last_message_at', None)

                return response
            except Exception as e:
                traceback.print_exc()
                raise e
    
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

                enriched_data = {
                    **data,
                    "sender_name": sender_entity.get('entity_name'),
                    "sender_entity_id": sender_entity.get('entity_id'),
                    "receiver_name": receiver_entity.get('entity_name'),
                    "receiver_entity_id": receiver_entity.get('entity_id'),
                }

                msg = MessageModel(**enriched_data)
                session.add(msg)
                await session.commit()

                await session.refresh(
                    msg,
                    attribute_names=["sender", "receiver"]
                )
                await msg.send_notification(enable=enable_notification)
                await self._emit_message_notifications(msg, sender, receiver)
                return "Message sent successfully."
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e
            except Exception as e:
                await session.rollback()
                traceback.print_exc()
                raise e

    async def _emit_message_notifications(self, msg: MessageModel, sender: UserModel, receiver: UserModel):
        try:
            sio = self._get_sio()
            payload = {
                'message_id': msg.message_id,
                'sender_id': msg.sender_id,
                'receiver_id': msg.receiver_id,
                'sender_name': msg.sender_name,
                'receiver_name': msg.receiver_name,
                'sender_entity_id': msg.sender_entity_id,
                'receiver_entity_id': msg.receiver_entity_id,
                'content': msg.content,
                'sent_at': msg.sent_at.isoformat(),
            }
            
            receiver_room = f"user:{receiver.user_id}"
            sender_room = f"user:{sender.user_id}"
            
            # Emit to receiver
            await sio.emit("new_message", payload, room=receiver_room, namespace="/")
            # Emit to sender (confirmation)
            await sio.emit("message_sent", payload, room=sender_room, namespace="/")
            
        except Exception as e:
            traceback.print_exc()
            raise e

    async def get_conversation_messages(self, user_id: str, partner_id: str, limit: int = 50, offset: int = 0):
        async with AsyncSession() as session:
            try:
                result = await session.execute(
                    select(MessageModel)
                    .where(
                        or_(
                            (MessageModel.sender_id == user_id) & (MessageModel.receiver_id == partner_id),
                            (MessageModel.sender_id == partner_id) & (MessageModel.receiver_id == user_id),
                        )
                    )
                    .order_by(desc(MessageModel.sent_at))
                    .limit(limit)
                    .offset(offset)
                )
                messages = result.scalars().all()
                
                # Enhanced message data with all necessary fields
                messages_data = []
                for msg in reversed(messages):
                    message_data = {
                        'message_id': msg.message_id,
                        'sender_id': msg.sender_id,
                        'receiver_id': msg.receiver_id,
                        'sender_name': msg.sender_name,
                        'receiver_name': msg.receiver_name,
                        'sender_entity_id': msg.sender_entity_id,
                        'receiver_entity_id': msg.receiver_entity_id,
                        'content': msg.content,
                        'sent_at': msg.sent_at.isoformat(),
                    }
                    messages_data.append(message_data)
                
                return {
                    "messages": messages_data,
                    "has_more": len(messages) == limit,
                    "total_count": len(messages)
                }
            except Exception as e:
                traceback.print_exc()
                raise e

    async def mark_messages_as_read(self, user_id: str, conversation_partner_id: str):
        async with AsyncSession() as session:
            try:
                return "Messages marked as read"
            except Exception as e:
                traceback.print_exc()
                raise e

    async def get_unread_message_count(self, user_id: str):
        async with AsyncSession() as session:
            try:
                return {"unread_count": 0}
            except Exception as e:
                traceback.print_exc()
                raise e

    async def delete_message(self, message_id: str, user_id: str):
        async with AsyncSession() as session:
            try:
                result = await session.execute(
                    select(MessageModel)
                    .where(MessageModel.message_id == message_id)
                )
                message = result.scalar_one_or_none()
                if not message:
                    raise ApiException("Message not found")
                if message.sender_id != user_id:
                    raise ApiException("Permission denied")
                await session.delete(message)
                await session.commit()
                sio = self._get_sio()
                deletion_payload = {
                    "type": "message_deleted",
                    "message_id": message_id,
                    "conversation_partner": message.receiver_id if message.sender_id == user_id else message.sender_id
                }
                sender_room = f"user:{message.sender_id}"
                receiver_room = f"user:{message.receiver_id}"
                await sio.emit("message_deleted", deletion_payload, room=sender_room, namespace="/")
                await sio.emit("message_deleted", deletion_payload, room=receiver_room, namespace="/")
                return "Message deleted successfully"
            except Exception as e:
                await session.rollback()
                traceback.print_exc()
                raise e