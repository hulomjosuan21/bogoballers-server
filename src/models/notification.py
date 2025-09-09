from __future__ import annotations
from asyncio import to_thread
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.models.user import UserModel
    
from datetime import datetime
import inspect
from sqlalchemy import String, ForeignKey, Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.extensions import Base
from src.utils.db_utils import CreatedAt, UUIDGenerator
from sqlalchemy.dialects.postgresql import JSONB 
from firebase_admin import messaging

notification_action_enum = SqlEnum(
    "team_join_request",
    "message_only",
    "announcement",
    "payment_failed",
    "payment_received",
    "team_invitation",
    name="notification_action_enum",
    create_type=True
)

notification_status_enum = SqlEnum(
    "unread",
    "read",
    name="notification_status_enum",
    create_type=True
)

class NotificationModel(Base):
    __tablename__ = "notifications_table"

    notification_id: Mapped[str] = UUIDGenerator("notification")
    
    action_type: Mapped[str] = mapped_column(
        notification_action_enum,
        nullable=False,
        default="message_only"
    )
    action_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    
    to_id: Mapped[str] = mapped_column(
        ForeignKey("users_table.user_id", ondelete="CASCADE"), 
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        notification_status_enum,
        nullable=False,
        default="unread"
    )

    created_at: Mapped[datetime] = CreatedAt()

    to_user: Mapped["UserModel"] = relationship("UserModel", foreign_keys=[to_id])

    async def send_notification(self, enable: bool = False):
        receiver_token = getattr(self.to_user, "fcm_token", None)
        
        if enable and receiver_token:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=self.title,
                    body=self.message
                ),
                token=receiver_token
            )
            await to_thread(messaging.send, message)
            
    def to_json(self):
        return {
            "notification_id": str(self.notification_id),
            "action_type": self.action_type,
            "action_payload": self.action_payload,
            "title": self.title,
            "message": self.message,
            "to_id": str(self.to_id),
            "status": self.status,
            "created_at": self.created_at.isoformat()
        }

_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]

