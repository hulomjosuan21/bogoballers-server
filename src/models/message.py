from __future__ import annotations
from asyncio import to_thread
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.models.user import UserModel
    
from sqlalchemy import ForeignKey, String, Text, CheckConstraint
from src.extensions import Base
from src.utils.db_utils import CreatedAt, UUIDGenerator
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import inspect
from src.extensions import Base
from firebase_admin import messaging

class MessageModel(Base):
    __tablename__ = "messages_table"
    
    __table_args__ = (
        CheckConstraint(
            "sender_id <> receiver_id",
            name="check_sender_receiver_not_equal"
        ),
    )
    
    message_id: Mapped[str] = UUIDGenerator("message")
    
    sender_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users_table.user_id", ondelete="CASCADE"),
        unique=False,
        nullable=False
    )
    sender_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_entity_id: Mapped[str] = mapped_column(String, nullable=False)
    
    receiver_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users_table.user_id", ondelete="CASCADE"),
        unique=False,
        nullable=False
    )
    receiver_name: Mapped[str] = mapped_column(String(255), nullable=False)
    receiver_entity_id: Mapped[str] = mapped_column(String, nullable=False)
    
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    sent_at: Mapped[datetime] = CreatedAt()
    
    sender: Mapped["UserModel"] = relationship(
        "UserModel",
        foreign_keys=[sender_id],
        passive_deletes=True
    )

    receiver: Mapped["UserModel"] = relationship(
        "UserModel",
        foreign_keys=[receiver_id],
        passive_deletes=True
    )
    
    def to_json(self) -> dict:
        return {
            'message_id': self.message_id,
            'sender_id': self.sender_id,
            'receiver_id': self.receiver_id,
            'sender_name': self.sender_name,
            'receiver_name': self.receiver_name,
            'sender_entity_id': self.sender_entity_id,
            'receiver_entity_id': self.receiver_entity_id,
            'content': self.content,
            'sent_at': self.sent_at.isoformat(),
        }
        
    async def send_notification(self, enable: bool = False):
        receiver_token = getattr(self.receiver, "fcm_token", None)
        
        if enable and receiver_token:
            print("Sending Notification")
            message = messaging.Message(
                notification=messaging.Notification(
                    title=f"From: {self.sender_name}",
                    body=self.content
                ),
                token=receiver_token
            )
            await to_thread(messaging.send, message)
            
        return self

_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]