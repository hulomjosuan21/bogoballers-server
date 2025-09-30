from __future__ import annotations
import inspect
from typing import Optional
from datetime import datetime
from sqlalchemy import (
    Float,
    String,
    ForeignKey,
    Enum as SqlEnum,
    DateTime,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.extensions import Base
from src.models.player import PlayerModel
from src.models.team import TeamModel, payment_status_enum
from src.models.league import LeagueCategoryModel
from src.utils.db_utils import CreatedAt, UUIDGenerator
from src.utils.mixins import UpdatableMixin
from sqlalchemy.dialects.postgresql import JSONB

guest_request_status_enum = SqlEnum(
    "Pending",
    "Accepted",
    "Rejected",
    name="guest_request_status_enum",
    create_type=True,
)

guest_request_type_enum = SqlEnum(
    "Team",
    "Player",
    name="guest_request_type_enum",
    create_type=True,
)


class GuestRegistrationRequestModel(Base, UpdatableMixin):
    __tablename__ = "guest_registration_requests_table"

    guest_request_id: Mapped[str] = UUIDGenerator("guest-req")

    league_category_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_categories_table.league_category_id", ondelete="CASCADE"),
        nullable=False
    )

    team_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("teams_table.team_id", ondelete="CASCADE"),
        nullable=True
    )
    player_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("players_table.player_id", ondelete="CASCADE"),
        nullable=True
    )

    request_type: Mapped[str] = mapped_column(
        guest_request_type_enum,
        nullable=False,
        comment="Specifies whether the request is for a 'Team' or a 'Player'."
    )
    status: Mapped[str] = mapped_column(
        guest_request_status_enum,
        default="Pending",
        nullable=False,
        comment="The current status of the request (Pending, Accepted, Rejected)."
    )

    amount_paid: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    payment_status: Mapped[str] = mapped_column(
        payment_status_enum,
        default="Pending",
        nullable=False
    )
    payment_record: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


    request_created_at: Mapped[datetime] = CreatedAt()
    request_processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the request was accepted or rejected."
    )

    league_category: Mapped["LeagueCategoryModel"] = relationship(lazy="joined")
    team: Mapped[Optional["TeamModel"]] = relationship(lazy="joined")
    player: Mapped[Optional["PlayerModel"]] = relationship(lazy="joined")

    __table_args__ = (
        # Ensures that a request is for EITHER a team OR a player, but not both or neither.
        CheckConstraint(
            "(request_type = 'Team' AND team_id IS NOT NULL AND player_id IS NULL) OR "
            "(request_type = 'Player' AND player_id IS NOT NULL AND team_id IS NULL)",
            name="chk_guest_request_entity"
        ),
        # Prevents a team from submitting multiple requests to the same category.
        UniqueConstraint("league_category_id", "team_id", name="uq_guest_team_request"),
        # Prevents a player from submitting multiple requests to the same category.
        UniqueConstraint("league_category_id", "player_id", name="uq_guest_player_request"),
    )

    def to_json(self) -> dict:
        data = {
            'guest_request_id': self.guest_request_id,
            'league_category_id': self.league_category_id,
            'request_type': self.request_type,
            'status': self.status,
            'amount_paid': self.amount_paid,
            'payment_status': self.payment_status,
            'payment_record': self.payment_record,
            'request_created_at': self.request_created_at.isoformat(),
            'request_processed_at': self.request_processed_at.isoformat() if self.request_processed_at else None,
            'league_category_name': self.league_category.category.category_name if self.league_category and self.league_category.category else None,
        }
        if self.request_type == "Team" and self.team:
            data['details'] = self.team.to_json()
        elif self.request_type == "Player" and self.player:
            data['details'] = self.player.to_json()
        return data

_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]
