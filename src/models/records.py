from typing import TYPE_CHECKING, List, Optional


if TYPE_CHECKING:
    from models.match import LeagueMatchModel
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
    league_match_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_matches_table.league_match_id", ondelete="CASCADE"),
        nullable=False
    )
    record_json: Mapped[List[dict]] = mapped_column(JSONB, nullable=False)
    record_created_at: Mapped[datetime] = CreatedAt()

    league_match: Mapped["LeagueMatchModel"] = relationship(
        "LeagueMatchModel",
        lazy="joined",
    )

    def to_json(self) -> dict:
        return {
            "record_id": self.record_id,
            "league_id": self.league_id,
            "league_match_id": self.league_match_id,
            "home_team": self.league_match.home_team.team.team_name,
            "away_team": self.league_match.away_team.team.team_name,
            "record_name": self.league_match.display_name,
            "schedule_date": self.league_match.scheduled_date.isoformat() if self.league_match.scheduled_date else None,
            "record_json": self.record_json,
            "record_created_at": self.record_created_at.isoformat(),
        }
  
_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]
