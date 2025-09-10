from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional


if TYPE_CHECKING:
    from src.models.league_admin import LeagueAdministratorModel, CategoryModel
    from src.models.team import LeagueTeamModel
    from src.models.league import LeagueCategoryModel
    
from datetime import datetime
from sqlalchemy import (
    ForeignKey, String, Boolean, Float, Integer, DateTime, Text,
    Enum as SqlEnum
)
from sqlalchemy.dialects.postgresql import JSONB, DATERANGE
from sqlalchemy.orm import Mapped, mapped_column, relationship
import inspect
from datetime import date
from src.extensions import Base
from src.utils.db_utils import CreatedAt, UpdatedAt, UUIDGenerator
from src.utils.mixins import UpdatableMixin

league_status_enum = SqlEnum(
    "Scheduled",
    "Ongoing",
    "Completed",
    "Postponed",
    "Cancelled",
    name="league_status_enum",
    create_type=False
)

class LeagueModel(Base, UpdatableMixin):
    __tablename__ = "leagues_table"

    league_id: Mapped[str] = UUIDGenerator("league")

    league_administrator_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_administrator_table.league_administrator_id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    league_title: Mapped[str] = mapped_column(String(250), nullable=False)
    league_description: Mapped[str] = mapped_column(Text, nullable=False)
    league_address: Mapped[str] = mapped_column(String(250), nullable=False)
    league_budget: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    league_courts: Mapped[List[dict]] = mapped_column(JSONB, nullable=False, default=list)
    league_officials: Mapped[List[dict]] = mapped_column(JSONB, nullable=False, default=list)
    league_referees: Mapped[List[dict]] = mapped_column(JSONB, nullable=False, default=list)
    league_affiliates: Mapped[List[dict]] = mapped_column(JSONB, nullable=False, default=list)

    registration_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opening_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    league_schedule: Mapped[tuple[date, date]] = mapped_column(
        DATERANGE,
        nullable=False
    )

    banner_url: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(
        league_status_enum,
        default="Scheduled",
        nullable=False
    )

    season_year: Mapped[int] = mapped_column(Integer, default=datetime.now().year, nullable=False)
    sportsmanship_rules: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    
    option: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()
    
    creator: Mapped["LeagueAdministratorModel"] = relationship(
        "LeagueAdministratorModel",
        cascade="all, delete",
        passive_deletes=True
    )

    categories: Mapped[list["LeagueCategoryModel"]] = relationship(
        "LeagueCategoryModel",
        back_populates="league",
        cascade="all, delete-orphan"
    )
    
    def _league_schedule_serialized(self, value):
        try:
            return [
                value[0].isoformat(),
                value[1].isoformat()
            ]
        except (TypeError, AttributeError):
            return [
                value.lower.isoformat(),
                value.upper.isoformat()
            ]

    def to_json_for_query_search(self) -> dict:
        return {
            "league_id": self.league_id,
            "league_administrator_id": self.league_administrator_id,
            "league_title": self.league_title,
            "league_description": self.league_description,
            "league_address": self.league_address,
            "league_budget": self.league_budget,
            "registration_deadline": self.registration_deadline.isoformat(),
            "opening_date": self.opening_date.isoformat(),
            "league_schedule": self._league_schedule_serialized(self.league_schedule),
            "banner_url": self.banner_url,
            "status": self.status,
            "season_year": self.season_year,
            "sportsmanship_rules": self.sportsmanship_rules,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "categories": [category.to_json_for_query_search() for category in (self.categories or [])],
            "creator": self.creator.to_json_for_query_search()
        }
    
    def to_json(self) -> dict:
        return {
            "league_id": self.league_id,
            "league_administrator_id": self.league_administrator_id,
            "league_title": self.league_title,
            "league_description": self.league_description,
            "league_address": self.league_address,
            "league_budget": self.league_budget,
            "registration_deadline": self.registration_deadline.isoformat(),
            "opening_date": self.opening_date.isoformat(),
            "league_schedule": self._league_schedule_serialized(self.league_schedule),
            "banner_url": self.banner_url,
            "status": self.status,
            "season_year": self.season_year,
            "sportsmanship_rules": self.sportsmanship_rules,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "categories": [category.to_json() for category in (self.categories or [])],
            "option": self.option
        }
        
    def to_json_for_analytics(self) -> dict:
        return {
            "league_id": self.league_id,
            "league_administrator_id": self.league_administrator_id,
            "league_title": self.league_title,
            "league_description": self.league_description,
            "league_address": self.league_address,
            "league_budget": self.league_budget,
            "registration_deadline": self.registration_deadline.isoformat(),
            "opening_date": self.opening_date.isoformat(),
            "league_schedule": self._league_schedule_serialized(self.league_schedule),
            "banner_url": self.banner_url,
            "status": self.status,
            "season_year": self.season_year,
            "sportsmanship_rules": self.sportsmanship_rules,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "categories": [category.to_json_for_analytics() for category in (self.categories or [])],
            "option": self.option            
        }
        
    def to_json_resource(self) -> dict:
        return {
            "league_id": self.league_id,
            "league_courts": self.league_courts,
            "league_officials": self.league_officials,
            "league_referees": self.league_referees,
            "league_affiliates": self.league_affiliates,
        }
        
class LeagueCategoryModel(Base, UpdatableMixin):
    __tablename__ = "league_categories_table"

    league_category_id: Mapped[str] = UUIDGenerator("league-category")
    
    category_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("categories_table.category_id", ondelete="CASCADE"),
        nullable=False
    )
    
    league_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("leagues_table.league_id", ondelete="CASCADE"),
        nullable=False
    )
    
    max_team: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    accept_teams: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()
    
    teams: Mapped[list["LeagueTeamModel"]] = relationship(
        "LeagueTeamModel", back_populates="category", cascade="all, delete-orphan"
    )
    
    league: Mapped["LeagueModel"] = relationship(
        "LeagueModel",
        back_populates="categories"
    )

    rounds: Mapped[list["LeagueCategoryRoundModel"]] = relationship(
        "LeagueCategoryRoundModel",
        back_populates="category",
        cascade="all, delete-orphan"
    )
    
    category: Mapped["CategoryModel"] = relationship(
        "CategoryModel",
        lazy="joined"
    )
    
    def to_json_for_query_search(self) -> dict:
        return {
            **self.category.to_json_league_category(),
            "league_category_id": self.league_category_id,
            "league_id": self.league_id,
            "max_team": self.max_team,
            "accept_teams": self.accept_teams,
            "rounds": [round_.to_json() for round_ in (self.rounds or [])]
        }
    
    def to_json(self) -> dict:
        return {
            **self.category.to_json_league_category(),
            "league_category_id": self.league_category_id,
            "league_id": self.league_id,
            "max_team": self.max_team,
            "accept_teams": self.accept_teams,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "rounds": [round_.to_json() for round_ in (self.rounds or [])]
        }
        
    def to_json_for_analytics(self) -> dict:
        return {
            **self.category.to_json_league_category(),
            "league_category_id": self.league_category_id,
            "league_id": self.league_id,
            "max_team": self.max_team,
            "accept_teams": self.accept_teams,
            "rounds": [round_.to_json_for_analytics() for round_ in (self.rounds or [])]
        }
        
    def to_json_for_league_player(self) -> dict:
        return {
            **self.category.to_json_league_category(),
            "league_category_id": self.league_category_id,
            "league_id": self.league_id,
        }
        
round_name_enum = SqlEnum(
    "Elimination",
    "Quarterfinal",
    "Semifinal",
    "Final",
    "Regular Season",
    "Exhibition",
    "Practice",
    name="round_name_enum",
    create_type=False
)

round_status_enum = SqlEnum(
    "Upcoming",
    "Ongoing",
    "Finished",
    name="round_status_enum",
    create_type=False
)

class LeagueCategoryRoundModel(Base, UpdatableMixin):
    __tablename__ = "league_category_rounds_table"

    round_id: Mapped[str] = mapped_column(String, nullable=False, primary_key=True)
    
    league_category_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_categories_table.league_category_id", ondelete="CASCADE"),
        nullable=False
    )

    round_name: Mapped[str] = mapped_column(round_name_enum, nullable=False)
    round_order: Mapped[int] = mapped_column(Integer, nullable=False)

    position: Mapped[dict] = mapped_column(JSONB, nullable=True)

    format_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # don't remove this
    round_format: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=None) # don't remove this this is for xyflow
    format_config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False
    )
    format_options: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False
    )
    
    matches_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    round_status: Mapped[str] = mapped_column(round_status_enum, default="Upcoming", nullable=False)

    next_round_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("league_category_rounds_table.round_id", ondelete="SET NULL"), nullable=True
    )

    category: Mapped["LeagueCategoryModel"] = relationship(
        "LeagueCategoryModel",
        back_populates="rounds"
    )

    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()

    def to_json(self) -> dict:
        return {
            "round_id": self.round_id,
            "league_category_id": self.league_category_id,
            "round_name": self.round_name,
            "round_order": self.round_order,
            "round_status": self.round_status,
            "matches_generated": self.matches_generated,
            "round_format": self.round_format or None,
            "format_config": self.format_config or None,
            "position": self.position,
            "next_round_id": self.next_round_id or None
        }
        
    def to_json_for_analytics(self) -> dict:
        return {
            "round_id": self.round_id,
            "league_category_id": self.league_category_id,
            "round_name": self.round_name,
            "matches_generated": self.matches_generated,
            "round_order": self.round_order,
            "round_status": self.round_status,
            "round_format": self.round_format or None,
            "position": self.position,
            "next_round_id": self.next_round_id or None
        }

_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]