from collections import defaultdict
from sqlalchemy import or_, select, desc, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload
from src.models.user import UserModel
from src.models.message import MessageModel
from src.extensions import AsyncSession
from src.utils.api_response import ApiException
from datetime import datetime
import traceback

class MessageService:
    def __init__(self):
        self._sio = None
    
    def _get_sio(self):
        """Lazy load socket.io instance to avoid circular imports"""
        if self._sio is None:
            from src.extensions import socket_service
            self._sio = socket_service.sio
        return self._sio

    async def get_conversations(self, user_id: str):
        """
        Get all conversations for a user, with messages sorted chronologically
        """
        async with AsyncSession() as session:
            try:
                print(f"🔍 Fetching conversations for user: {user_id}")
                
                # Get all messages involving this user
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
                    .order_by(MessageModel.sent_at.asc())  # Chronological order
                )
                messages = result.scalars().all()

                print(f"📊 Found {len(messages)} total messages")

                # Group messages by conversation partner
                conversations = defaultdict(list)

                for msg in messages:
                    try:
                        # Determine the other party in the conversation
                        if msg.sender_id == user_id:
                            other_id = msg.receiver_entity_id
                            other_name = msg.receiver_name
                            other_user_id = msg.receiver_id
                        else:
                            other_id = msg.sender_entity_id
                            other_name = msg.sender_name
                            other_user_id = msg.sender_id

                        # Use entity_id as the conversation key for consistency
                        conversation_key = other_id or other_user_id

                        conversations[conversation_key].append({
                            "message": msg.to_json_message_only(),
                            "user_id": other_user_id,
                            "entity_id": other_id,
                            "name": other_name or "Unknown User",
                        })
                    except Exception as e:
                        print(f"⚠️ Error processing message {msg.message_id}: {e}")
                        continue

                # Build response with conversations sorted by most recent message
                response = []
                for conversation_key, msgs in conversations.items():
                    if not msgs:
                        continue
                        
                    try:
                        # Get metadata from first message
                        meta = msgs[0]
                        
                        # Extract just the message data
                        messages_data = [m["message"] for m in msgs]
                        
                        # Sort messages by timestamp to ensure chronological order
                        messages_data.sort(key=lambda x: x.get('sent_at', ''))
                        
                        conversation = {
                            "conversation_with": {
                                "user_id": meta["user_id"],
                                "entity_id": meta["entity_id"],
                                "name": meta["name"],
                            },
                            "messages": messages_data,
                            "last_message_at": messages_data[-1].get('sent_at') if messages_data else None,
                        }
                        
                        response.append(conversation)
                        
                    except Exception as e:
                        print(f"⚠️ Error building conversation for key {conversation_key}: {e}")
                        continue

                # Sort conversations by most recent message (most recent first)
                response.sort(
                    key=lambda x: x.get('last_message_at', ''),
                    reverse=True
                )
                
                # Remove the helper field from response
                for conv in response:
                    conv.pop('last_message_at', None)

                print(f"✅ Returning {len(response)} conversations")
                return response
                
            except Exception as e:
                print(f"❌ Error in get_conversations: {e}")
                traceback.print_exc()
                raise e
    
    async def send_message_notification(self, data: dict, enable_notification: bool) -> str:
        async with AsyncSession() as session:
            try:
                print(f"Data: {data}")
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

                print(f"✅ Message saved with ID: {msg.message_id}")

                await msg.send_notification(enable=True)

                await self._emit_message_notifications(msg, sender, receiver)

                return "Message sent successfully."

            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                print(f"❌ Database error: {e}")
                raise e
            except Exception as e:
                await session.rollback()
                print(f"❌ Unexpected error: {e}")
                traceback.print_exc()
                raise e

    async def _emit_message_notifications(self, msg: MessageModel, sender: UserModel, receiver: UserModel):
        """
        Emit socket notifications for new message
        """
        try:
            # Get socket instance lazily
            sio = self._get_sio()
            
            # Prepare payload with full message data
            payload = msg.to_json()  # This should include all message fields
            
            print(f"🔄 Emitting socket notifications for message: {msg.message_id}")

            # Define rooms
            receiver_room = f"user:{receiver.user_id}"
            sender_room = f"user:{sender.user_id}"
            
            # Entity rooms (if applicable)
            if msg.receiver_entity_id:
                conv_room_receiver = f"entity:{msg.receiver_entity_id}"
            else:
                conv_room_receiver = None
                
            if msg.sender_entity_id:
                conv_room_sender = f"entity:{msg.sender_entity_id}"
            else:
                conv_room_sender = None

            # Emit to receiver (they should see the new message)
            await sio.emit("new_message", payload, room=receiver_room, namespace="/")
            print(f"📨 Emitted new_message to receiver room: {receiver_room}")

            # Emit to sender (confirmation that message was processed)
            await sio.emit("message_sent", payload, room=sender_room, namespace="/")
            print(f"✅ Emitted message_sent to sender room: {sender_room}")

            # Also emit new_message to sender so their conversation list updates
            await sio.emit("new_message", payload, room=sender_room, namespace="/")

            # Emit to entity rooms if they exist
            if conv_room_receiver:
                await sio.emit("conversation_update", payload, room=conv_room_receiver, namespace="/")
                print(f"🔄 Emitted conversation_update to receiver entity room: {conv_room_receiver}")
                
            if conv_room_sender and conv_room_sender != conv_room_receiver:
                await sio.emit("conversation_update", payload, room=conv_room_sender, namespace="/")
                print(f"🔄 Emitted conversation_update to sender entity room: {conv_room_sender}")

            print("🎯 All socket notifications emitted successfully")

        except Exception as e:
            print(f"❌ Socket emission error: {e}")
            traceback.print_exc()
            # Re-raise to let caller know about the failure
            raise e

    async def get_conversation_messages(self, user_id: str, partner_id: str, limit: int = 50, offset: int = 0):
        """
        Get messages between two users with pagination
        """
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
                
                # Convert to JSON and reverse to get chronological order (oldest first)
                messages_data = [msg.to_json_message_only() for msg in reversed(messages)]
                
                return {
                    "messages": messages_data,
                    "has_more": len(messages) == limit,
                    "total_count": len(messages)
                }
                
            except Exception as e:
                print(f"❌ Error getting conversation messages: {e}")
                traceback.print_exc()
                raise e

    async def mark_messages_as_read(self, user_id: str, conversation_partner_id: str):
        """
        Mark all messages from a conversation partner as read
        """
        async with AsyncSession() as session:
            try:
                # This would require a 'read_at' or 'is_read' field in your MessageModel
                # Implementation depends on your schema
                
                # Example if you have a read_at field:
                # await session.execute(
                #     update(MessageModel)
                #     .where(
                #         (MessageModel.sender_id == conversation_partner_id) &
                #         (MessageModel.receiver_id == user_id) &
                #         (MessageModel.read_at.is_(None))
                #     )
                #     .values(read_at=datetime.utcnow())
                # )
                # await session.commit()
                
                print(f"📖 Marked messages as read for user {user_id} from {conversation_partner_id}")
                return "Messages marked as read"
                
            except Exception as e:
                print(f"❌ Error marking messages as read: {e}")
                traceback.print_exc()
                raise e

    async def get_unread_message_count(self, user_id: str):
        """
        Get count of unread messages for a user
        """
        async with AsyncSession() as session:
            try:
                # This would require a 'read_at' or 'is_read' field in your MessageModel
                # Example implementation:
                
                # result = await session.execute(
                #     select(func.count(MessageModel.message_id))
                #     .where(
                #         (MessageModel.receiver_id == user_id) &
                #         (MessageModel.read_at.is_(None))
                #     )
                # )
                # 
                # count = result.scalar() or 0
                # return {"unread_count": count}
                
                # Placeholder return
                return {"unread_count": 0}
                
            except Exception as e:
                print(f"❌ Error getting unread count: {e}")
                traceback.print_exc()
                raise e

    async def delete_message(self, message_id: str, user_id: str):
        """
        Delete a message (soft delete or hard delete based on your requirements)
        """
        async with AsyncSession() as session:
            try:
                # Get the message first to verify ownership
                result = await session.execute(
                    select(MessageModel)
                    .where(MessageModel.message_id == message_id)
                )
                
                message = result.scalar_one_or_none()
                
                if not message:
                    raise ApiException("Message not found")
                    
                # Verify user has permission to delete (sender only)
                if message.sender_id != user_id:
                    raise ApiException("Permission denied")
                
                # Perform deletion (you might want soft delete instead)
                await session.delete(message)
                await session.commit()
                
                # Emit socket notification for deletion
                sio = self._get_sio()
                deletion_payload = {
                    "type": "message_deleted",
                    "message_id": message_id,
                    "conversation_partner": message.receiver_id if message.sender_id == user_id else message.sender_id
                }
                
                # Notify both parties
                sender_room = f"user:{message.sender_id}"
                receiver_room = f"user:{message.receiver_id}"
                
                await sio.emit("message_deleted", deletion_payload, room=sender_room, namespace="/")
                await sio.emit("message_deleted", deletion_payload, room=receiver_room, namespace="/")
                
                return "Message deleted successfully"
                
            except Exception as e:
                await session.rollback()
                print(f"❌ Error deleting message: {e}")
                traceback.print_exc()
                raise e