from typing import TYPE_CHECKING, List, Optional


if TYPE_CHECKING:
    from src.models.player import PlayerModel
    
from datetime import datetime
import inspect
from sqlalchemy import Boolean, ForeignKey, Integer, String
from src.extensions import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from src.utils.db_utils import UUIDGenerator, UpdatedAt

class PlayerValidDocument(Base):
    __tablename__ = "player_valid_documents_table"

    doc_id: Mapped[str] = UUIDGenerator("doc")
    player_id: Mapped[str] = mapped_column(
        ForeignKey("players_table.player_id", ondelete="CASCADE"), nullable=False
    )

    document_type: Mapped[str] = mapped_column(String(100), nullable=False)

    document_urls: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    document_format: Mapped[str] = mapped_column(String(20), default="single")

    uploaded_at: Mapped[datetime] = UpdatedAt()
    
    def to_json(self):
        return {
            'doc_id': self.doc_id,
            'player_id': self.player_id,
            'document_type': self.document_type,
            'document_urls': self.document_urls or [],
            'document_format': self.document_format,
            'uploaded_at': self.uploaded_at.isoformat()
        }
    
_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]