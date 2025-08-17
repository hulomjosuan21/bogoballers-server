from __future__ import annotations
from sqlalchemy import String, Boolean, Integer, DateTime, Enum as SqlEnum, Text, ARRAY, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.extensions import Base
from src.utils.db_utils import CreatedAt, UUIDGenerator, UpdatedAt
from src.models.league import round_name_enum

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

    match_id: Mapped[str] = UUIDGenerator("match")

    round_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("league_category_rounds_table.round_id", ondelete="CASCADE"),
        nullable=True
    )

    league_id: Mapped[str] = mapped_column(String, nullable=False)
    division_id: Mapped[str | None] = mapped_column(String, nullable=True)

    home_team_id: Mapped[str] = mapped_column(String, nullable=False)
    away_team_id: Mapped[str] = mapped_column(String, nullable=False)

    home_team_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_team_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    winner_team_id: Mapped[str | None] = mapped_column(String, nullable=True)
    loser_team_id: Mapped[str | None] = mapped_column(String, nullable=True)

    scheduled_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=40)

    court: Mapped[str | None] = mapped_column(String, nullable=True)
    referees: Mapped[list[str]] = mapped_column(ARRAY(String), default=[])

    category: Mapped[str] = mapped_column(
        round_name_enum,
        nullable=False,
        default="Elimination"
    )

    status: Mapped[str] = mapped_column(
        match_status_enum,
        nullable=False,
        default="Unscheduled"
    )

    match_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)

    round_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bracket_side: Mapped[str | None] = mapped_column(String, nullable=True)
    bracket_position: Mapped[str | None] = mapped_column(String, nullable=True)

    previous_match_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=[])
    next_match_id: Mapped[str | None] = mapped_column(String, nullable=True)
    next_match_slot: Mapped[str | None] = mapped_column(String, nullable=True)

    loser_next_match_id: Mapped[str | None] = mapped_column(String, nullable=True)
    loser_next_match_slot: Mapped[str | None] = mapped_column(String, nullable=True)

    pairing_method: Mapped[str | None] = mapped_column(String, nullable=True)
    generated_by: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)

    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    is_third_place: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[DateTime] = CreatedAt()
    updated_at: Mapped[DateTime] = UpdatedAt()

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
