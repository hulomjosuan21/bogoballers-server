import inspect
from src.extensions import Base
from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from typing import Optional
from src.utils.db_utils import CreatedAt, UUIDGenerator

class LeagueLogModel(Base):
    __tablename__ = "league_logs_table"

    league_log_id: Mapped[str] = UUIDGenerator("l-log")
    
    league_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("leagues_table.league_id", ondelete="CASCADE"),
        nullable=True
    )

    round_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("league_category_rounds_table.round_id", ondelete="CASCADE"),
        nullable=True 
    )

    team_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("league_teams_table.league_team_id", ondelete="CASCADE"),
        nullable=True
    )

    action_type: Mapped[str] = mapped_column(String, nullable=False) 
    
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    meta_data: Mapped[dict] = mapped_column(JSONB, default={}, nullable=True)
    
    log_created_at: Mapped[datetime] = CreatedAt()
    
_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]