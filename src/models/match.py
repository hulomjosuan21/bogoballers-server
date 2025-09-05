from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, DateTime, Enum as SqlEnum, Text, ARRAY, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.extensions import Base
from src.utils.db_utils import CreatedAt, UUIDGenerator, UpdatedAt
from src.models.league import round_name_enum
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

    # 🏷️ Identifiers & Relations
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

    # 👥 Teams & Results
    home_team_id: Mapped[str | None] = mapped_column(String, nullable=True)
    away_team_id: Mapped[str | None] = mapped_column(String, nullable=True)

    home_team_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_team_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    winner_team_id: Mapped[str | None] = mapped_column(String, nullable=True)
    loser_team_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # 📅 Scheduling & Logistics
    scheduled_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=40)
    court: Mapped[str | None] = mapped_column(String, nullable=True)
    referees: Mapped[list[str]] = mapped_column(JSONB, default=[])

    # ⚙️ Format & Rules
    match_format: Mapped[str] = mapped_column(
        String,  # e.g. "RoundRobin", "Knockout", "DoubleElim", "BestOf"
        default="Knockout",
        nullable=False
    )
    format_config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False
    )
    # Examples:
    # Round Robin:   { "group": "A", "rounds": 1 }
    # Knockout:      { "elimination_side": "winner" }
    # Best of Three: { "best_of": 3, "current_game": 1 }
    # Twice to Beat: { "advantage_team_id": "team123" }

    # 🔀 Progression / Bracket Flow
    previous_match_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=[])
    next_match_id: Mapped[str | None] = mapped_column(String, nullable=True)
    next_match_slot: Mapped[str | None] = mapped_column(String, nullable=True)  # "home" or "away"

    loser_next_match_id: Mapped[str | None] = mapped_column(String, nullable=True)
    loser_next_match_slot: Mapped[str | None] = mapped_column(String, nullable=True)

    # 📝 Meta & Display
    round_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bracket_side: Mapped[str | None] = mapped_column(String, nullable=True)   # "Winners", "Losers"
    bracket_position: Mapped[str | None] = mapped_column(String, nullable=True)
    pairing_method: Mapped[str | None] = mapped_column(String, nullable=False, default='random') # "seeded", "random", "manual"
    generated_by: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # ✅ Flags & Status
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    is_third_place: Mapped[bool] = mapped_column(Boolean, default=False)
    is_exhibition: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(
        match_status_enum,
        nullable=False,
        default="Unscheduled"
    )

    # 🕒 Audit
    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()

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

    __table_args__ = (
        UniqueConstraint(
            "league_id",
            "category",
            "division_id",
            "round_number",
            "home_team_id",
            "away_team_id",
            name="unique_match_per_category_and_division"
        ),
    )
