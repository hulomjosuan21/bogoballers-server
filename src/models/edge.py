import inspect
from typing import Optional
from sqlalchemy import ForeignKey, String
from src.extensions import Base
from src.utils.db_utils import UUIDGenerator
from sqlalchemy.orm import Mapped, mapped_column

from src.utils.mixins import SerializationMixin

class LeagueFlowEdgeModel(Base, SerializationMixin):
    __tablename__ = "league_flow_edges_table"

    edge_id: Mapped[str] = UUIDGenerator("ledge")
    league_id: Mapped[str] = mapped_column(
        String, ForeignKey("leagues_table.league_id", ondelete="CASCADE"), nullable=False
    )
    
    league_category_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_categories_table.league_category_id", ondelete="CASCADE"),
        nullable=False
    )

    source_node_id: Mapped[str] = mapped_column(String, nullable=False)
    target_node_id: Mapped[str] = mapped_column(String, nullable=False)
    source_handle: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    target_handle: Mapped[Optional[str]] = mapped_column(String, nullable=True)

_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]