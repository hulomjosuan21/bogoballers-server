from __future__ import annotations
from asyncio import to_thread
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.models.user import UserModel
    
from datetime import datetime
import inspect
from sqlalchemy import String, ForeignKey, DateTime, Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.user import account_type_enum
from src.utils.db_utils import CreatedAt, UUIDGenerator
from src.extensions import Base, SERVICE_ACCOUNT_PATH
from firebase_admin import credentials, messaging
import firebase_admin

cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred)

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
    action_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    
    image_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    to_id: Mapped[str] = mapped_column(ForeignKey("users_table.user_id"), nullable=False)
    from_id: Mapped[str] = mapped_column(ForeignKey("users_table.user_id"), nullable=False)

    status: Mapped[str] = mapped_column(
        notification_status_enum,
        nullable=False,
        default="unread"
    )

    created_at: Mapped[datetime] = CreatedAt()

    to_user: Mapped["UserModel"] = relationship("UserModel", foreign_keys=[to_id])
    from_user: Mapped["UserModel"] = relationship("UserModel", foreign_keys=[from_id])

    async def send(self, token: str):
        message_kwargs = {
            "notification": messaging.Notification(
                title=self.title,
                body=self.message
            ),
            "token": token
        }

        if self.image_url:
            message_kwargs["data"] = {"image": str(self.image_url)}

        message = messaging.Message(**message_kwargs)
        
        response = await to_thread(messaging.send, message)
        
        return response

    def is_unread(self) -> bool:
        return self.status == "unread"

    def __repr__(self) -> str:
        return f"<Notification(id={self.notification_id}, action_type={self.action_type}, to={self.to_id}, status={self.status})>"
        
_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]

