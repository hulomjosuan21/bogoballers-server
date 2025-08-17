from __future__ import annotations
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.models.league_admin import LeagueAdministratorModel
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

    league_title: Mapped[str] = mapped_column(String(100), nullable=False)
    league_description: Mapped[str] = mapped_column(Text, nullable=False)
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
    
    creator: Mapped["LeagueAdministratorModel"] = relationship("LeagueAdministratorModel")

    categories: Mapped[list["LeagueCategoryModel"]] = relationship(
        "LeagueCategoryModel",
        back_populates="league",
        cascade="all, delete-orphan"
    )
    
    def to_json(self) -> dict:
        def to_iso(value):
            if isinstance(value, (datetime, date)):
                return value.isoformat()
            return value

        league_schedule_serialized = None
        if self.league_schedule:
            try:
                league_schedule_serialized = [
                    to_iso(self.league_schedule[0]),
                    to_iso(self.league_schedule[1])
                ]
            except (TypeError, AttributeError):
                league_schedule_serialized = [
                    to_iso(self.league_schedule.lower),
                    to_iso(self.league_schedule.upper)
                ]

        return {
            "league_id": self.league_id,
            "league_administrator_id": self.league_administrator_id,
            "league_title": self.league_title,
            "league_description": self.league_description,
            "league_budget": self.league_budget,
            "registration_deadline": to_iso(self.registration_deadline),
            "opening_date": to_iso(self.opening_date),
            "league_schedule": league_schedule_serialized,
            "banner_url": self.banner_url,
            "status": self.status,
            "season_year": self.season_year,
            "sportsmanship_rules": self.sportsmanship_rules,
            "created_at": to_iso(self.created_at),
            "updated_at": to_iso(self.updated_at),
            "categories": [category.to_json() for category in (self.categories or [])],
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
        
class LeagueCategoryModel(Base):
    __tablename__ = "league_categories_table"

    category_id: Mapped[str] = UUIDGenerator("league-category")
    
    league_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("leagues_table.league_id", ondelete="CASCADE"),
        nullable=False
    )

    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    max_team: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    accept_teams: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    team_entrance_fee_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    individual_player_entrance_fee_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)

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
    
    def to_json(self) -> dict:
        return {
            "category_id": self.category_id,
            "league_id": self.league_id,
            "category_name": self.category_name,
            "max_team": self.max_team,
            "accept_teams": self.accept_teams,
            "team_entrance_fee_amount": self.team_entrance_fee_amount,
            "individual_player_entrance_fee_amount": self.individual_player_entrance_fee_amount,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "rounds": [round_.to_json() for round_ in (self.rounds or [])]
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

round_format_enum = SqlEnum(
    "Round Robin",
    "Knockout",
    "Double Elimination",
    "Twice-to-Beat",
    "Best-of-3",
    "Best-of-5",
    "Best-of-7",
    name="round_format_enum",
    create_type=False
)

class LeagueCategoryRoundModel(Base):
    __tablename__ = "league_category_rounds_table"

    round_id: Mapped[str] = mapped_column(String, nullable=False, primary_key=True)
    
    category_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_categories_table.category_id", ondelete="CASCADE"),
        nullable=False
    )

    round_name: Mapped[str] = mapped_column(round_name_enum, nullable=False)

    round_order: Mapped[int] = mapped_column(Integer, nullable=False)
    
    round_format: Mapped[str] = mapped_column(round_format_enum , nullable=True)
    
    position: Mapped[dict] = mapped_column(JSONB, nullable=True)

    round_status: Mapped[str] = mapped_column(round_status_enum, default="Upcoming", nullable=False)

    category: Mapped["LeagueCategoryModel"] = relationship(
        "LeagueCategoryModel",
        back_populates="rounds"
    )

    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()

    def to_json(self) -> dict:
        return {
            "round_id": self.round_id,
            "category_id": self.category_id,
            "round_name": self.round_name,
            "round_order": self.round_order,
            "round_status": self.round_status,
            "round_format": self.round_format,
            "position": self.position,
        }

_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]