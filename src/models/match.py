from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Boolean, Integer, DateTime, Enum as SqlEnum, Text, ARRAY, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.league import LeagueModel
from src.models.team import LeagueTeamModel, TeamModel
from src.extensions import Base
from src.utils.db_utils import CreatedAt, PublicIDGenerator, UUIDGenerator, UpdatedAt
from sqlalchemy.dialects.postgresql import JSONB

from src.utils.mixins import UpdatableMixin

match_status_enum = SqlEnum(
    "Unscheduled",
    "Scheduled",
    "In Progress",
    "Completed",
    "Cancelled",
    "Postponed",
    name="match_status_enum",
    create_type=False
)

class LeagueMatchModel(Base, UpdatableMixin):
    __tablename__ = "league_matches_table"
    league_match_id: Mapped[str] = UUIDGenerator("lmatch")
    public_league_match_id: Mapped[str] = PublicIDGenerator("lm")

    league_id: Mapped[str] = mapped_column(String, ForeignKey("leagues_table.league_id", ondelete="CASCADE"), nullable=False)
    league_category_id: Mapped[str] = mapped_column(String, ForeignKey("league_categories_table.league_category_id", ondelete="CASCADE"), nullable=False)
    round_id: Mapped[str] = mapped_column(String, ForeignKey("league_category_rounds_table.round_id", ondelete="CASCADE"), nullable=False)

    home_team_id: Mapped[str] = mapped_column(String, ForeignKey("league_teams_table.league_team_id"), nullable=True)
    away_team_id: Mapped[str] = mapped_column(String, ForeignKey("league_teams_table.league_team_id"), nullable=True)
    
    home_team: Mapped[Optional["LeagueTeamModel"]] = relationship(
        "LeagueTeamModel",
        foreign_keys=[home_team_id],
        uselist=False,
        lazy="joined"
    )

    away_team: Mapped[Optional["LeagueTeamModel"]] = relationship(
        "LeagueTeamModel",
        foreign_keys=[away_team_id],
        uselist=False,
        lazy="joined"
    )

    home_team_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_team_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    winner_team_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    loser_team_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    scheduled_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    quarters: Mapped[int] = mapped_column(Integer, default=4)
    minutes_per_quarter: Mapped[int] = mapped_column(Integer, default=10)
    minutes_per_overtime: Mapped[int] = mapped_column(Integer, default=5)
    court: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    referees: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    previous_match_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=[])
    next_match_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    next_match_slot: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    loser_next_match_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    loser_next_match_slot: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    round_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # bracket_side: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # bracket_position: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pairing_method: Mapped[str] = mapped_column(String, nullable=False, default="random")
    generated_by: Mapped[str] = mapped_column(String, nullable=False, default="system")
    generated_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    is_runner_up: Mapped[bool] = mapped_column(Boolean, default=False)
    is_third_place: Mapped[bool] = mapped_column(Boolean, default=False)
    
    is_elimination: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(match_status_enum, nullable=False, default="Unscheduled")
    
    league: Mapped["LeagueModel"] = relationship(
        "LeagueModel",
        foreign_keys=[league_id],
        uselist=False,
        lazy="joined"
    )
    
    stage_number = mapped_column(Integer, nullable=True)
    
    group_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("league_groups_table.group_id", ondelete="SET NULL"),
        nullable=True
    )
    
    position: Mapped[dict] = mapped_column(JSONB, nullable=True)
    
    depends_on_match_ids: Mapped[List[str]] = mapped_column(ARRAY(String), default=[])
    is_placeholder: Mapped[bool] = mapped_column(Boolean, default=False)
    bracket_stage_label: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    league_match_created_at: Mapped[datetime] = CreatedAt()
    league_match_updated_at: Mapped[datetime] = UpdatedAt()

    __table_args__ = (
        UniqueConstraint(
            "league_id",
            "league_category_id",
            "round_number",
            "stage_number",
            "home_team_id",
            "away_team_id",
            name="unique_league_match_per_round"
        ),
    )

    def to_json(self) -> dict:
        def wrap_int(v):
            return int(v) if v is not None else None

        def wrap_str(v):
            return str(v) if v is not None else None

        def wrap_bool(v):
            return bool(v) if v is not None else False

        def wrap_list_str(v):
            return [str(x) for x in v] if v else []

        def wrap_datetime(v):
            return v.isoformat() if v else None

        return {
            "league_match_id": wrap_str(self.league_match_id),
            "public_league_match_id": wrap_str(self.public_league_match_id),
            "league_id": wrap_str(self.league_id),
            "league_category_id": wrap_str(self.league_category_id),
            "round_id": wrap_str(self.round_id),

            "home_team_id": wrap_str(self.home_team_id),
            "home_team": self.home_team.to_json() if self.home_team else None,
            "away_team_id": wrap_str(self.away_team_id),
            "away_team": self.away_team.to_json() if self.away_team else None,

            "home_team_score": wrap_int(self.home_team_score),
            "away_team_score": wrap_int(self.away_team_score),

            "winner_team_id": wrap_str(self.winner_team_id),
            "loser_team_id": wrap_str(self.loser_team_id),

            "group_id": wrap_str(self.group_id),
            
            "scheduled_date": wrap_datetime(self.scheduled_date),
            "quarters": wrap_int(self.quarters),
            "minutes_per_quarter": wrap_int(self.minutes_per_quarter),
            "minutes_per_overtime": wrap_int(self.minutes_per_overtime),

            "court": wrap_str(self.court),
            "referees": wrap_list_str(self.referees),
            "previous_match_ids": wrap_list_str(self.previous_match_ids),

            "next_match_id": wrap_str(self.next_match_id),
            "next_match_slot": wrap_str(self.next_match_slot),
            "loser_next_match_id": wrap_str(self.loser_next_match_id),
            "loser_next_match_slot": wrap_str(self.loser_next_match_slot),

            "round_number": wrap_int(self.round_number),
            "pairing_method": wrap_str(self.pairing_method),
            "generated_by": wrap_str(self.generated_by),
            "display_name": wrap_str(self.display_name),

            "is_final": wrap_bool(self.is_final),
            "is_third_place": wrap_bool(self.is_third_place),
            "is_runner_up": wrap_bool(self.is_runner_up),
            "is_elimination": wrap_bool(self.is_elimination),
            "status": wrap_str(self.status),
            "league": self.league.to_json(),

            "stage_number": wrap_int(self.stage_number),
            "depends_on_match_ids": wrap_list_str(self.depends_on_match_ids),
            "is_placeholder": wrap_bool(self.is_placeholder),
            "bracket_stage_label": wrap_str(self.bracket_stage_label),

            "league_match_created_at": wrap_datetime(self.league_match_created_at),
            "league_match_updated_at": wrap_datetime(self.league_match_updated_at),
        }


class MatchModel(Base, UpdatableMixin):
    __tablename__ = "matches_table"
    
    match_id: Mapped[str] = UUIDGenerator("match")
    public_match_id: Mapped[str] = PublicIDGenerator("m")

    home_team_id: Mapped[str] = mapped_column(String, ForeignKey("teams_table.team_id"), nullable=False)
    away_team_id: Mapped[str] = mapped_column(String, ForeignKey("teams_table.team_id"), nullable=False)

    home_team: Mapped["TeamModel"] = relationship(
        "TeamModel",
        foreign_keys=[home_team_id],
        uselist=False,
        lazy="joined"
    )

    away_team: Mapped["TeamModel"] = relationship(
        "TeamModel",
        foreign_keys=[away_team_id],
        uselist=False,
        lazy="joined"
    )

    home_team_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_team_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    scheduled_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    quarters: Mapped[int] = mapped_column(Integer, default=4)
    minutes_per_quarter: Mapped[int] = mapped_column(Integer, default=10)
    court: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    referees: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    is_exhibition: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(match_status_enum, nullable=False, default="Unscheduled")

    match_created_at: Mapped[datetime] = CreatedAt()
    match_updated_at: Mapped[datetime] = UpdatedAt()

    def to_json(self) -> dict:
        return {
            'match_id': self.match_id,
            'public_match_id': self.public_match_id,
            'home_team_id': self.home_team_id,
            'home_team': self.home_team.to_json(),
            'away_team_id': self.away_team_id,
            'away_team': self.away_team.to_json(),
            'home_team_score': self.home_team_score or None,
            'away_team_score': self.away_team_score or None,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'quarters': self.quarters,
            'minutes_per_quarter': self.minutes_per_quarter,
            'court': self.court or None,
            'referees': self.referees,
            'is_exhibition': self.is_exhibition,
            'status': self.status,
            'match_created_at': self.match_created_at.isoformat(),
            'match_updated_at': self.match_updated_at.isoformat()
        }
