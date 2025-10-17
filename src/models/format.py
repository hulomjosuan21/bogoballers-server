from __future__ import annotations
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from src.models.league import LeagueCategoryRoundModel
    
import inspect
from sqlalchemy import Boolean, ForeignKey, String
from src.extensions import Base
from src.models.match_types import RoundConfig, parse_round_config
from src.utils.mixins import SerializationMixin
from src.utils.db_utils import CreatedAt, UUIDGenerator, UpdatedAt
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property

class LeagueRoundFormatModel(Base, SerializationMixin):
    __tablename__ = "league_round_format_table"

    format_id: Mapped[str] = UUIDGenerator("lformat")
    
    round_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_category_rounds_table.round_id", ondelete="CASCADE"),
        unique=True,
        nullable=True
    )

    format_name: Mapped[str] = mapped_column(String, nullable=False)
    format_type: Mapped[str] = mapped_column(String, nullable=False)
    format_obj: Mapped[str] = mapped_column(JSONB, nullable=True)
    is_configured: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    
    position: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    round: Mapped["LeagueCategoryRoundModel"] = relationship(
        "LeagueCategoryRoundModel",
        back_populates="format",
        uselist=False,
        lazy="joined"
    )
    
    @hybrid_property
    def parsed_format_obj(self) -> Optional[RoundConfig]:
        if not self.format_obj:
            return None
        try:
            return parse_round_config(self.format_obj)
        except (ValueError, TypeError):
            return None
    
_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]