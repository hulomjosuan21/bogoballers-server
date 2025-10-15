from datetime import datetime
import inspect
from sqlalchemy import ForeignKey, String
from src.extensions import Base
from src.utils.mixins import SerializationMixin
from src.utils.db_utils import CreatedAt, UUIDGenerator, UpdatedAt
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

class LeagueRoundFormatModel(Base, SerializationMixin):
    __tablename__ = "league_round_format_table"

    format_id: Mapped[str] = UUIDGenerator("lgroup")
    
    round_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_category_rounds_table.round_id", ondelete="CASCADE"),
        nullable=False
    )

    league_category_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_categories_table.league_category_id", ondelete="CASCADE"),
        nullable=False
    )
    
    format_name: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(JSONB, nullable=False, default={})
    
    position: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]