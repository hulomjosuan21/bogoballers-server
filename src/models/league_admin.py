from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.user import UserModel
    from src.models.league import LeagueModel
    
from datetime import datetime
from sqlalchemy import ForeignKey, String, Boolean, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
import inspect

from src.extensions import Base
from src.utils.db_utils import CreatedAt, UpdatedAt, UUIDGenerator

class CategoryModel(Base):
    category_id = Mapped[str] = UUIDGenerator("league_administrator")

class LeagueAdministratorModel(Base):
    __tablename__ = "league_administrator_table"

    league_administrator_id: Mapped[str] = UUIDGenerator("league_administrator")

    is_allowed: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=False,
        server_default=text("false")
    )

    is_operational: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=True,
        server_default=text("true")
    )
    
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users_table.user_id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    organization_type: Mapped[str] = mapped_column(String, nullable=False)
    organization_name: Mapped[str] = mapped_column(String(200), nullable=False)
    organization_address: Mapped[str] = mapped_column(String(250), nullable=False)

    organization_photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    organization_logo_url: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()
    
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="league_administrator")
    
    leagues: Mapped[list["LeagueModel"]] = relationship(
        "LeagueModel",
        back_populates="creator",
        cascade="all, delete-orphan"
    )
    
    @property
    def active_league(self) -> "LeagueModel | None":
        return next(
            (league for league in self.leagues if league.status in ["Scheduled", "Ongoing"]),
            None
        )
    
    def to_json(self) -> dict:
        return {
            "user_id": self.user_id,
            "league_administrator_id": self.league_administrator_id,
            "organization_name": self.organization_name,
            "organization_type": self.organization_type,
            "organization_address": self.organization_address,
            "organization_logo_url": self.organization_logo_url,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "user": self.user.to_json(),
        }

_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]