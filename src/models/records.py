from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from src.models.league import LeagueModel
import datetime
from src.extensions import Base
from sqlalchemy import (
    ForeignKey,
    String,
    Enum as SqlEnum
)
import inspect
from datetime import  datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from src.utils.db_utils import CreatedAt, UUIDGenerator

class LeagueMatchRecordModel(Base):
    __tablename__ = "league_match_records_table"
    record_id: Mapped[str] = UUIDGenerator("record")
    league_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("leagues_table.league_id", ondelete="CASCADE"),
        nullable=False
    )
    record_name: Mapped[str] = mapped_column(String(250), nullable=False)
    record_json: Mapped[List[dict]] = mapped_column(JSONB, nullable=False)
    record_created_at: Mapped[datetime] = CreatedAt()

    def to_json(self) -> dict:
        return {
            "record_id": self.record_id,
            "league_id": self.league_id,
            "record_name": self.record_name,
            "record_json": self.record_json,
            "record_created_at": self.record_created_at.isoformat(),
        }
  
_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]
