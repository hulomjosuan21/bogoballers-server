from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from src.utils.mixins import UpdatableMixin

if TYPE_CHECKING:
    from src.models.user import UserModel
    from src.models.league import LeagueModel
    
from datetime import datetime
from sqlalchemy import Float, ForeignKey, Integer, String, Boolean, Text, text, Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import inspect

from src.extensions import Base
from src.utils.db_utils import CreatedAt, UpdatedAt, UUIDGenerator

category_allowed_gender_enum = SqlEnum(
    "Male",
    "Female",
    "Any",
    name="category_allowed_gender_enum",
    create_type=True
)
class CategoryModel(Base, UpdatableMixin):
    __tablename__ = "categories_table"
    category_id: Mapped[str] = UUIDGenerator("category")
    category_name: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    league_administrator_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_administrator_table.league_administrator_id", ondelete="CASCADE"),
        nullable=False
    )
    
    check_player_age: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=True,
    )
    player_min_age: Mapped[Optional[int]] = mapped_column(Integer,  nullable=True) 
    player_max_age: Mapped[Optional[int]] = mapped_column(Integer,  nullable=True)
    player_gender: Mapped[str] = mapped_column(category_allowed_gender_enum, nullable=False)
    check_address: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=True,
    )
    allowed_address: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    
    allow_guest_team: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    team_entrance_fee_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    allow_guest_player: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    guest_player_fee_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    
    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()
        
    def to_json_league_category(self):
        return {
            'category_id': self.category_id,
            'category_name': self.category_name,
            'check_player_age': self.check_player_age,
            'player_min_age': self.player_min_age if self.player_min_age is not None else None,
            'player_max_age': self.player_max_age if self.player_max_age is not None else None,
            'player_gender': self.player_gender,
            'check_address': self.check_address,
            'allowed_address': self.allowed_address or None,
            'allow_guest_team': self.allow_guest_team,
            'team_entrance_fee_amount': self.team_entrance_fee_amount,
            'allow_guest_player': self.allow_guest_player,
            'guest_player_fee_amount': self.guest_player_fee_amount
        }
        
    def to_json(self):
        return {
            'category_id': self.category_id,
            'category_name': self.category_name,
            'league_administrator_id': self.league_administrator_id,
            'check_player_age': self.check_player_age,
            'player_min_age': self.player_min_age if self.player_min_age is not None else None,
            'player_max_age': self.player_max_age if self.player_max_age is not None else None,
            'player_gender': self.player_gender,
            'check_address': self.check_address,
            'allowed_address': self.allowed_address or None,
            'allow_guest_team': self.allow_guest_team,
            'team_entrance_fee_amount': self.team_entrance_fee_amount,
            'allow_guest_player': self.allow_guest_player,
            'guest_player_fee_amount': self.guest_player_fee_amount,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
        
class LeagueAdministratorModel(Base, UpdatableMixin):
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
    organization_name: Mapped[str] = mapped_column(String(250), nullable=False)
    organization_address: Mapped[str] = mapped_column(String(250), nullable=False)

    organization_photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    organization_logo_url: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()
    
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="league_administrator")
    
    categories: Mapped[list["CategoryModel"]] = relationship(
        "CategoryModel",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="CategoryModel.updated_at.desc()"
    )
    
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
        
    def categories_list(self) -> list:
        return [category.to_json() for category in getattr(self, "categories", [])]
    
    def to_json_for_query_search(self) -> dict:
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