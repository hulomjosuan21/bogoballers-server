from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional


if TYPE_CHECKING:
    from src.models.records import LeagueMatchRecordModel
    from src.models.team import LeagueTeamModel
    from src.models.league_admin import LeagueAdministratorModel
    from src.models.league import LeagueCategoryModel
    from src.models.category import CategoryModel
    from src.models.format import LeagueRoundFormatModel
    
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
from src.utils.db_utils import CreatedAt, PublicIDGenerator, UpdatedAt, UUIDGenerator
from src.utils.mixins import UpdatableMixin
from sqlalchemy.ext.hybrid import hybrid_property

league_status_enum = SqlEnum(
    "Pending",
    "Scheduled",
    "Ongoing",
    "Completed",
    "Rejected",
    "Postponed",
    "Cancelled",
    name="league_status_enum",
    create_type=False
)

class LeagueModel(Base, UpdatableMixin):
    __tablename__ = "leagues_table"

    league_id: Mapped[str] = UUIDGenerator("league")
    public_league_id: Mapped[str] = PublicIDGenerator("l")

    league_administrator_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_administrator_table.league_administrator_id", ondelete="CASCADE"),
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
        default="Pending",
        nullable=False
    )

    season_year: Mapped[int] = mapped_column(Integer, default=datetime.now().year, nullable=False)
    sportsmanship_rules: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    
    league_created_at: Mapped[datetime] = CreatedAt()
    league_updated_at: Mapped[datetime] = UpdatedAt()
    
    creator: Mapped["LeagueAdministratorModel"] = relationship(
        "LeagueAdministratorModel",
        cascade="all, delete",
        passive_deletes=True,
        lazy="joined"
    )

    categories: Mapped[list["LeagueCategoryModel"]] = relationship(
        "LeagueCategoryModel",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    teams: Mapped[list["LeagueTeamModel"]] = relationship(
        "LeagueTeamModel",
        cascade="all, delete-orphan",
        lazy="selectin",
        back_populates="league"
    )
    
    league_match_records: Mapped[list["LeagueMatchRecordModel"]] = relationship(
        "LeagueMatchRecordModel",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def _league_schedule_serialized(self):
        try:
            return [
                self.league_schedule[0].isoformat(),
                self.league_schedule[1].isoformat()
            ]
        except (TypeError, AttributeError):
            return [
                self.league_schedule.lower.isoformat(),
                self.league_schedule.upper.isoformat()
            ]
            
    def to_json(self, include_team = False, include_record = False) -> dict:
        data = {
            'league_id': self.league_id,
            'public_league_id': self.public_league_id,
            'league_administrator_id': self.league_administrator_id,
            'league_title': self.league_title,
            'league_description': self.league_description,
            'league_address': self.league_address,
            'league_budget': self.league_budget,
            'league_courts': self.league_courts,
            'league_officials': self.league_officials,
            'league_referees': self.league_referees,
            'league_affiliates': self.league_affiliates,
            'registration_deadline': self.registration_deadline.isoformat(),
            'opening_date': self.opening_date.isoformat(),
            'league_schedule': self._league_schedule_serialized(),
            'banner_url': self.banner_url,
            'status': self.status,
            'season_year': self.season_year,
            'sportsmanship_rules': self.sportsmanship_rules,
            'league_created_at': self.league_created_at.isoformat(),
            'league_updated_at': self.league_updated_at.isoformat(),
            'creator': self.creator.to_json(),
            'league_categories': [c.to_json() for c in self.categories]
        }
        
        if include_team is True:
            data["teams"] = [team.to_json() for team in self.teams]

        if include_record is True:
            data["league_match_records"] = [
                record.to_json() for record in self.league_match_records
            ]
        
        return data


league_category_status_enum = SqlEnum(
    "Close",
    "Open",
    "Ongoing",
    "Completed",
    name="league_category_status_enum",
    create_type=True
)

class LeagueCategoryModel(Base, UpdatableMixin):
    __tablename__ = "league_categories_table"

    league_category_id: Mapped[str] = UUIDGenerator("league-category")
    public_league_category_id: Mapped[str] = PublicIDGenerator("lc")
    
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
    
    category: Mapped["CategoryModel"] = relationship(
        "CategoryModel",
        lazy="joined"
    )

    rounds: Mapped[list["LeagueCategoryRoundModel"]] = relationship(
        "LeagueCategoryRoundModel",
        back_populates="league_category",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LeagueCategoryRoundModel.round_order.asc()"
    )
    
    teams: Mapped[list["LeagueTeamModel"]] = relationship(
        "LeagueTeamModel",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    position: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    league_category_status: Mapped[Optional[str]] = mapped_column(league_category_status_enum, default="Close", nullable=False)
    
    manage_automatic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    max_team: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    accept_teams: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    league_category_created_at: Mapped[datetime] = CreatedAt()
    league_category_updated_at: Mapped[datetime] = UpdatedAt()
    
    def to_json(self) -> dict:
        return {
            **self.category.to_json(),
            'league_category_id': self.league_category_id,
            'league_id': self.league_id,
            'max_team': self.max_team,
            'league_category_status': self.league_category_status,
            'manage_automatic': self.manage_automatic,
            'accept_teams': self.accept_teams,
            'league_category_created_at': self.league_category_created_at.isoformat(),
            'league_category_updated_at': self.league_category_updated_at.isoformat(),
            'rounds': [round_.to_json() for round_ in self.rounds]
        }
    
round_status_enum = SqlEnum(
    "Upcoming",
    "Ongoing",
    "Finished",
    "Cancelled",
    "Postponed",
    name="round_status_enum",
    create_type=False
)

round_name_enum = SqlEnum(
    "Elimination",
    "Quarterfinal",
    "Semifinal",
    "Final",
    name="round_name_enum",
    create_type=False
)

class LeagueCategoryRoundModel(Base, UpdatableMixin):
    __tablename__ = "league_category_rounds_table"

    round_id: Mapped[str] = UUIDGenerator("lround")
    public_round_id: Mapped[str] = PublicIDGenerator('r')
    
    league_category_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_categories_table.league_category_id", ondelete="CASCADE"),
        nullable=False
    )

    round_name: Mapped[str] = mapped_column(round_name_enum, nullable=False)
    round_order: Mapped[int] = mapped_column(Integer, nullable=False)

    position: Mapped[dict] = mapped_column(JSONB, nullable=True)
    format: Mapped[Optional["LeagueRoundFormatModel"]] = relationship(
        "LeagueRoundFormatModel",
        back_populates="round",
        uselist=False,
        lazy="joined"
    )
    current_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    matches_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    round_status: Mapped[str] = mapped_column(round_status_enum, default="Upcoming", nullable=False)

    next_round_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("league_category_rounds_table.round_id", ondelete="SET NULL"), nullable=True
    )
    
    league_category: Mapped["LeagueCategoryModel"] = relationship(
        "LeagueCategoryModel",
        back_populates="rounds",
        foreign_keys=[league_category_id],
        lazy="selectin" 
    )
    
    @hybrid_property
    def total_stages(self) -> int:
        if not self.format:
            return 1
        parsed = self.format.parsed_format_obj
        if not parsed:
            return 1

        if hasattr(parsed, "stages"):
            return len(parsed.stages)
        elif hasattr(parsed, "total_stages"):
            return parsed.total_stages
        else:
            return 1

    def to_json(self) -> dict:
        return {
            'round_id': self.round_id,
            'public_round_id': self.public_round_id,
            'league_category_id': self.league_category_id,
            'round_name': self.round_name,
            'round_order': self.round_order,
            'round_status': self.round_status,
            'matches_generated': self.matches_generated,
            'format': self.format.to_dict() if self.format else None,
            'position': self.position if self.position else None,
            'total_stages': self.total_stages,
            'current_stage': self.current_stage,
            'next_round_id': self.next_round_id if self.next_round_id else None,
        }

_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]