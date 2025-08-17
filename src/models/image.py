from __future__ import annotations
from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
import inspect
from src.extensions import Base
from src.utils.db_utils import CreatedAt, UUIDGenerator
from datetime import datetime

class Image(Base):
    __tablename__ = 'images_url_table'
    id: Mapped[str] = UUIDGenerator("img")
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    image_url: Mapped[str] = mapped_column(String, nullable=False)
    tag: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = CreatedAt()

    __table_args__ = (
        Index('league_trophies_idx', 'entity_id', 'tag'),
    )

    def to_json(self):
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "image_url": self.image_url,
            "tag": self.tag,
            "uploaded_at": self.uploaded_at.isoformat()
        }
        
_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]