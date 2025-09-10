from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from src.models.player import LeaguePlayerModel
    from src.models.user import UserModel
    from src.models.player import PlayerTeamModel
    from src.models.league import LeagueModel, LeagueCategoryModel
    
from datetime import datetime
from sqlalchemy import (
    CheckConstraint, Float, ForeignKey, String, Boolean, Integer, Enum as SqlEnum, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
import inspect
from src.extensions import Base
from src.utils.db_utils import CreatedAt, UpdatedAt, UUIDGenerator
from src.utils.mixins import UpdatableMixin

class TeamModel(Base, UpdatableMixin):
    __tablename__ = "teams_table"

    team_id: Mapped[str] = UUIDGenerator("team")

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

    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()
    
    user: Mapped["UserModel"] = relationship("UserModel")
    players: Mapped[List["PlayerTeamModel"]] = relationship(
        "PlayerTeamModel",
        back_populates="team",
        foreign_keys="[PlayerTeamModel.team_id]"
    )
    
    def to_json_for_query_search(self) -> dict:
        return {
            'team_id': self.team_id,
            'user_id': self.user_id,
            'team_name': self.team_name,
            'team_address': self.team_address,
            'contact_number': self.contact_number,
            'team_motto': self.team_motto if self.team_motto else None,
            'team_logo_url': self.team_logo_url,
            'championships_won': self.championships_won,
            'coach_name': self.coach_name,
            'assistant_coach_name': self.assistant_coach_name if self.assistant_coach_name else None,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'total_draws': self.total_draws,
            'total_points': self.total_points,
            'is_recruiting': self.is_recruiting,
            'team_category': self.team_category or None,
            'user': self.user.to_json(),
        }
    
    def to_json_for_team_manager(self) -> dict:
        return {
            'team_id': self.team_id,
            'user_id': self.user_id,
            'team_name': self.team_name,
            'team_address': self.team_address,
            'contact_number': self.contact_number,
            'team_motto': self.team_motto if self.team_motto else None,
            'team_logo_url': self.team_logo_url,
            'championships_won': self.championships_won,
            'coach_name': self.coach_name,
            'assistant_coach_name': self.assistant_coach_name if self.assistant_coach_name else None,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'total_draws': self.total_draws,
            'total_points': self.total_points,
            'is_recruiting': self.is_recruiting,
            'team_category': self.team_category or None,
            'user': self.user.to_json(),
            'accepted_players': [
                player_team.to_json_for_team() for player_team in self.players if player_team.is_accepted == "Accepted"
            ],
            'pending_players': [
                player_team.to_json_for_team() for player_team in self.players if player_team.is_accepted == "Pending"
            ],
            'rejected_players': [
                player_team.to_json_for_team() for player_team in self.players if player_team.is_accepted == "Rejected"
            ],
            'invited_players': [
                player_team.to_json_for_team() for player_team in self.players if player_team.is_accepted == "Invited"
            ],
        }
        
    def to_json_for_league_team(self):
        return {
            'team_id': self.team_id,
            'user_id': self.user_id,
            'team_name': self.team_name,
            'team_address': self.team_address,
            'contact_number': self.contact_number,
            'team_motto': self.team_motto if self.team_motto else None,
            'team_logo_url': self.team_logo_url,
            'championships_won': self.championships_won,
            'coach_name': self.coach_name,
            'team_category': self.team_category or None,
            'assistant_coach_name': self.assistant_coach_name if self.assistant_coach_name else None,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'total_draws': self.total_draws,
            'total_points': self.total_points,
            'is_recruiting': self.is_recruiting,
            'user': self.user.to_json(),
        }
        
    def to_json(self) -> dict:
        return {
            'team_id': self.team_id,
            'user_id': self.user_id,
            'team_name': self.team_name,
            'team_address': self.team_address,
            'contact_number': self.contact_number,
            'team_motto': self.team_motto if self.team_motto else None,
            'team_logo_url': self.team_logo_url,
            'championships_won': self.championships_won,
            'coach_name': self.coach_name,
            'team_category': self.team_category or None,
            'assistant_coach_name': self.assistant_coach_name if self.assistant_coach_name else None,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'total_draws': self.total_draws,
            'total_points': self.total_points,
            'is_recruiting': self.is_recruiting,
            'user': self.user.to_json(),
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
    name="payment_status_enum",
    create_type=False
)

class LeagueTeamModel(Base, UpdatableMixin):
    __tablename__ = "league_teams_table"

    league_team_id: Mapped[str] = UUIDGenerator("league-team")
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
    draws: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        CheckConstraint("wins >= 0", name="check_wins_positive"),
        CheckConstraint("losses >= 0", name="check_losses_positive"),
        CheckConstraint("draws >= 0", name="check_draws_positive"),
        CheckConstraint("points >= 0", name="check_points_positive"),
        UniqueConstraint("team_id", "league_id", name="uq_team_per_league"),
    )

    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()
    
    category: Mapped["LeagueCategoryModel"] = relationship(
        "LeagueCategoryModel", back_populates="teams"
    )
    team: Mapped["TeamModel"] = relationship("TeamModel")
    league: Mapped["LeagueModel"] = relationship("LeagueModel")

    league_players: Mapped[List["LeaguePlayerModel"]] = relationship(
        "LeaguePlayerModel",
        back_populates="league_team",
        cascade="all, delete-orphan"
    )

    def to_json(self) -> dict:
        team_json = self.team.to_json_for_league_team()

        team_json["accepted_players"] = [
            player_team.to_json_for_team()
            for player_team in self.team.players
            if player_team.is_accepted == "Accepted"
        ]

        return {
            **team_json,
            "league_team_id": self.league_team_id,
            "league_id": self.league_id,
            "league_category_id": self.league_category_id,
            "status": self.status,
            "amount_paid": self.amount_paid,
            "payment_status": self.payment_status,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "points": self.points,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    def to_json_for_league(self) -> dict:
        team_json = self.team.to_json_for_league_team()
        
        return {
            **team_json,
            "league_team_id": self.league_team_id,
            "league_id": self.league_id,
            "league_category_id": self.league_category_id,
            "team": self.team.to_json_for_league_team(),
            "status": self.status,
            "amount_paid": self.amount_paid,
            "payment_status": self.payment_status,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "points": self.points,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "league_players": [player.to_json() for player in self.league_players]
        }
        
    def to_json_for_league_player(self) -> dict:
        team_json = self.team.to_json_for_league_team()
        
        return {
            **team_json,
            "league_team_id": self.league_team_id,
            "league_id": self.league_id,
            "league_category_id": self.league_category_id,
            "status": self.status,
            "amount_paid": self.amount_paid,
            "payment_status": self.payment_status,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "points": self.points,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        
    def to_json_for_match(self) -> dict:
        team_json = self.team.to_json_for_league_team()
        
        return {
            **team_json,
            "league_team_id": self.league_team_id,
            "league_id": self.league_id,
            "league_category_id": self.league_category_id,
            "status": self.status,
            "amount_paid": self.amount_paid,
            "payment_status": self.payment_status,
            "wins": self.wins,
            "losses": self.losses,
            "league_players": [player.to_json() for player in self.league_players],
            "draws": self.draws,
            "points": self.points,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]