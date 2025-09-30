from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from src.models.player import LeaguePlayerModel
    from src.models.user import UserModel
    from src.models.player import PlayerTeamModel
    from src.models.league import LeagueModel, LeagueCategoryModel
    
from datetime import datetime
from sqlalchemy import (
    CheckConstraint, DateTime, Float, ForeignKey, String, Boolean, Integer, Enum as SqlEnum, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
import inspect
from src.extensions import Base
from src.utils.db_utils import CreatedAt, PublicIDGenerator, UpdatedAt, UUIDGenerator
from src.utils.mixins import UpdatableMixin

class TeamModel(Base, UpdatableMixin):
    __tablename__ = "teams_table"

    team_id: Mapped[str] = UUIDGenerator("team")
    public_team_id: Mapped[str] = PublicIDGenerator("t")

    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users_table.user_id", ondelete="CASCADE"),
        nullable=False
    )
    team_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    team_address: Mapped[str] = mapped_column(String(250), nullable=False)
    team_category: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    contact_number: Mapped[str] = mapped_column(String(15), nullable=False)
    team_motto: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    team_logo_url: Mapped[str] = mapped_column(Text, nullable=False)
    championships_won: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coach_name: Mapped[str] = mapped_column(String(100), nullable=False)
    assistant_coach_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    total_wins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_losses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_draws: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_recruiting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    team_created_at: Mapped[datetime] = CreatedAt()
    team_updated_at: Mapped[datetime] = UpdatedAt()
    
    user: Mapped["UserModel"] = relationship("UserModel",lazy="joined")
    players: Mapped[List["PlayerTeamModel"]] = relationship(
        "PlayerTeamModel",
        back_populates="team",
        foreign_keys="[PlayerTeamModel.team_id]",
        lazy="selectin"
    )
    
    def to_json(self) -> dict:
        return {
            'team_id': self.team_id,
            'public_team_id': self.public_team_id,
            'user_id':  self.user_id,
            'team_name':  self.team_name,
            'team_address': self.team_address,
            'team_category': self.team_category or None,
            'contact_number': self.contact_number,
            'team_motto': self.team_motto or None,
            'team_logo_url': self.team_logo_url,
            'championships_won': self.championships_won,
            'coach_name': self.coach_name,
            'assistant_coach_name': self.assistant_coach_name or None,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'total_draws': self.total_draws,
            'total_points': self.total_points,
            'is_recruiting': self.is_recruiting,   
            'creator': self.user.to_json(),
            'team_created_at': self.team_created_at.isoformat(),
            'team_updated_at':self.team_updated_at.isoformat(),
            'accepted_players': [
                player.to_json() for player in self.players
                if player.is_accepted in ["Accepted", "Guest"]
            ],
            'pending_players': [
                p.to_json() for p in self.players if p.is_accepted == "Pending"
            ],
            'rejected_players': [
                p.to_json() for p in self.players if p.is_accepted == "Rejected"
            ],
            'invited_players': [
                p.to_json() for p in self.players if p.is_accepted == "Invited"
            ],
            'stanby_players': [
                p.to_json() for p in self.players if p.is_accepted == "Standby"
            ],
            'guest_players': [
                p.to_json() for p in self.players if p.is_accepted == "Guest"
            ],
        }
        
league_team_status_enum = SqlEnum(
    "Pending",
    "Accepted",
    "Rejected",
    name="league_team_status_enum",
    create_type=False
)

payment_status_enum = SqlEnum(
    "Pending",
    "Paid Online",
    "Paid On Site",
    "No Charge",
    "Refunded",
    "Partially Refunded",
    name="payment_status_enum",
    create_type=False
)

class LeagueTeamModel(Base, UpdatableMixin):
    __tablename__ = "league_teams_table"

    league_team_id: Mapped[str] = UUIDGenerator("league-team")
    league_team_public_id: Mapped[str] = PublicIDGenerator("lt")
    team_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("teams_table.team_id", ondelete="CASCADE"),
        nullable=False
    )
    
    league_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("leagues_table.league_id", ondelete="CASCADE"),
        unique=False,
        nullable=False
    )
    
    league_category_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_categories_table.league_category_id", ondelete="CASCADE"),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        league_team_status_enum,
        default="Pending",
        nullable=False
    )
    
    is_eliminated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    amount_paid: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    payment_status: Mapped[str] = mapped_column(
        payment_status_enum,
        default="Pending",
        nullable=False
    )
    payment_record: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    wins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    losses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    draws: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    __table_args__ = (
        CheckConstraint("wins >= 0", name="check_wins_positive"),
        CheckConstraint("losses >= 0", name="check_losses_positive"),
        CheckConstraint("draws >= 0", name="check_draws_positive"),
        CheckConstraint("points >= 0", name="check_points_positive"),
        UniqueConstraint("team_id", "league_id", name="uq_team_per_league"),
    )

    final_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_champion: Mapped[bool] = mapped_column(Boolean, default=False)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    eliminated_in_round_id: Mapped[Optional[str]] = mapped_column(ForeignKey("league_category_rounds_table.round_id", ondelete="SET NULL"), nullable=True)
    
    group_label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    league_team_created_at: Mapped[datetime] = CreatedAt()
    league_team_updated_at: Mapped[datetime] = UpdatedAt()
    
    team: Mapped["TeamModel"] = relationship("TeamModel", lazy="joined")

    league_players: Mapped[List["LeaguePlayerModel"]] = relationship(
        "LeaguePlayerModel",
        back_populates="league_team",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    def to_json(self, include_players: bool = True) -> dict:
        data = {
            'league_team_id': self.league_team_id,
            'league_team_public_id': self.league_team_public_id,
            'league_id': self.league_id,
            'league_category_id': self.league_category_id,
            'status': self.status,
            'is_eliminated': self.is_eliminated,
            'amount_paid': self.amount_paid,
            'payment_status': self.payment_status,
            'wins': self.wins,
            'losses': self.losses,
            'draws': self.draws,
            'points': self.points,
            'group_label': self.group_label,
            'final_rank': self.final_rank if self.final_rank else None,
            'is_champion': self.is_champion,
            'finalized_at': self.finalized_at.isoformat() if self.finalized_at else None,
            'league_team_created_at': self.league_team_created_at.isoformat(),
            'league_team_updated_at': self.league_team_updated_at.isoformat(),
            **self.team.to_json(),
        }

        if include_players:
            data['league_players'] = [player.to_json() for player in self.league_players]

        return data

_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]