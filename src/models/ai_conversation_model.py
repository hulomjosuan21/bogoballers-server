from datetime import datetime
import inspect
from sqlalchemy import ForeignKey, String, Text, Enum as SqlEnum
from src.extensions import Base
from src.utils.db_utils import CreatedAt, UUIDGenerator
from sqlalchemy.orm import Mapped, mapped_column

ai_basketball_mentor_role_enum = SqlEnum(
    "user",
    "coach",
    name="ai_basketball_mentor_role_enum",
    create_type=True
)

class AIConversationModel(Base):
    __tablename__ = "ai_conversation_table"

    convo_id: Mapped[str] = UUIDGenerator("ai")
    user_id: Mapped[str] = mapped_column(ForeignKey("users_table.user_id", ondelete="CASCADE"))
    message_role: Mapped[str] = mapped_column(ai_basketball_mentor_role_enum, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    convo_created_at: Mapped[datetime] = CreatedAt()
    
_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]