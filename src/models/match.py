from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, DateTime, Enum as SqlEnum, Text, ARRAY, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, object_session
from src.models.team import LeagueTeamModel, TeamModel
from src.extensions import Base
from src.utils.db_utils import CreatedAt, UUIDGenerator, UpdatedAt
from sqlalchemy.dialects.postgresql import JSONB

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

class MatchModel(Base):
    __tablename__ = "matches_table"

    # note: Identifiers & Relations
    match_id: Mapped[str] = UUIDGenerator("match")

    league_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("leagues_table.league_id", ondelete="CASCADE"),
        nullable=True
    )
    league_category_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("league_categories_table.league_category_id", ondelete="CASCADE"),
        nullable=True
    )
    round_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("league_category_rounds_table.round_id", ondelete="CASCADE"),
        nullable=True
    )

    # note: Teams & Results
    home_team_id: Mapped[str | None] = mapped_column(String, nullable=True)
    home_team_type: Mapped[str | None] = mapped_column(
        String,  # "league" or "team"
        nullable=True
    )

    away_team_id: Mapped[str | None] = mapped_column(String, nullable=True)
    away_team_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    home_team_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_team_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    winner_team_id: Mapped[str | None] = mapped_column(String, nullable=True)
    loser_team_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # note: Scheduling & Logistics
    scheduled_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=40)
    court: Mapped[str | None] = mapped_column(String, nullable=True)
    referees: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False
    )

    # note: Progression / Bracket Flow
    previous_match_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=[])
    next_match_id: Mapped[str | None] = mapped_column(String, nullable=True)
    next_match_slot: Mapped[str | None] = mapped_column(String, nullable=True)  # "home" or "away"

    loser_next_match_id: Mapped[str | None] = mapped_column(String, nullable=True)
    loser_next_match_slot: Mapped[str | None] = mapped_column(String, nullable=True)

    # note: Meta & Display
    round_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bracket_side: Mapped[str | None] = mapped_column(String, nullable=True)   # "Winners", "Losers"
    bracket_position: Mapped[str | None] = mapped_column(String, nullable=True)
    pairing_method: Mapped[str | None] = mapped_column(String, nullable=False, default='random')
    generated_by: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # note: Flags & Status
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    is_third_place: Mapped[bool] = mapped_column(Boolean, default=False)
    is_exhibition: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(
        match_status_enum,
        nullable=False,
        default="Unscheduled"
    )
    
    @property
    def home_team(self):
        if self.home_team_type == "league":
            return object_session(self).get(LeagueTeamModel, self.home_team_id)
        elif self.home_team_type == "team":
            return object_session(self).get(TeamModel, self.home_team_id)
        return None

    @property
    def away_team(self):
        if self.away_team_type == "league":
            return object_session(self).get(LeagueTeamModel, self.away_team_id)
        elif self.away_team_type == "team":
            return object_session(self).get(TeamModel, self.away_team_id)
        return None

    # note: Audit
    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()

    # note: Constraints
    __table_args__ = (
        UniqueConstraint(
            "league_id",
            "league_category_id",
            "round_number",
            "home_team_id",
            "away_team_id",
            name="unique_match_per_round"
        ),
    )