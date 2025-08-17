from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
import inspect

from src.extensions import Base
from src.utils.db_utils import CreatedAt, UUIDGenerator

class EntityLogModel(Base):
    __tablename__ = "entity_logs_table"

    log_id: Mapped[str] = UUIDGenerator("entity_log")

    entity_id: Mapped[str] = mapped_column(String, nullable=False)

    message: Mapped[str] = mapped_column(Text, nullable=False)

    timestamp: Mapped[datetime] = CreatedAt()


_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]