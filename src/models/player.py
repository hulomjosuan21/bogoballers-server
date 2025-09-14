from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional


if TYPE_CHECKING:
    from src.models.league import LeagueCategoryModel
    from src.models.user import UserModel
    from src.models.team import TeamModel
    from src.models.league import LeagueTeamModel, LeagueModel
    
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Float, Integer, Date, ForeignKey, Enum as SqlEnum, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
import inspect
from datetime import date, datetime
from src.extensions import Base
from src.utils.db_utils import CreatedAt, PublicIDGenerator, UpdatedAt, UUIDGenerator
from src.utils.mixins import UpdatableMixin

player_gender_enum = SqlEnum(
    "Male",
    "Female",
    name="player_gender_enum",
    create_type=True
)

class PlayerModel(Base, UpdatableMixin):
    __tablename__ = "players_table"

    player_id: Mapped[str] = UUIDGenerator("player")
    
    public_player_id: Mapped[str] = PublicIDGenerator("p")

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users_table.user_id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    full_name: Mapped[str] = mapped_column(String(250), nullable=False)
    profile_image_url: Mapped[str] = mapped_column(Text, nullable=False)
    
    gender: Mapped[str] = mapped_column(player_gender_enum, nullable=False)
    birth_date: Mapped[Date] = mapped_column(Date, nullable=False)
    player_address: Mapped[str] = mapped_column(String(250), nullable=False)

    jersey_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    jersey_number: Mapped[float] = mapped_column(Float, nullable=False)
    position: Mapped[List[str]] = mapped_column(JSONB, nullable=False)

    height_in: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    total_games_played: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_points_scored: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_assists: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_rebounds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_join_league: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_ban: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    valid_documents: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)

    player_created_at: Mapped[datetime] = CreatedAt()
    player_updated_at: Mapped[datetime] = UpdatedAt()
    
    player_teams: Mapped[List["PlayerTeamModel"]] = relationship(
        "PlayerTeamModel",
        back_populates="player",
        lazy="selectin"
    )
    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="player",
        lazy="joined"
    )
    
    def to_json(self) -> dict:
        return {
            'player_id': self.player_id,
            'public_player_id': self.public_player_id,
            'user_id': self.user_id,
            'full_name': self.full_name,
            'profile_image_url': self.profile_image_url,
            'gender': self.gender,
            'birth_date': self.birth_date,
            'player_address': self.player_address,
            'jersey_name': self.jersey_name,
            'jersey_number': self.jersey_number,
            'position': self.position,
            'height_in': self.height_in,
            'weight_kg': self.weight_kg,
            'total_games_played': self.total_games_played,
            'total_points_scored': self.total_points_scored,
            'total_assists': self.total_assists,
            'total_rebounds': self.total_rebounds,
            'total_join_league': self.total_join_league,
            'is_ban': self.is_ban,
            'is_allowed': self.is_allowed,
            'valid_documents': self.valid_documents,
            'user': self.user.to_json(),
            'player_created_at': self.player_created_at.isoformat(),
            'player_updated_at': self.player_updated_at.isoformat(),
        }
    
player_is_accepted_enum = SqlEnum(
    "Pending",
    "Accepted",
    "Rejected",
    "Invited",
    "Standby",
    "Guest",
    name="player_is_accepted_enum",
    create_type=True,
)

class PlayerTeamModel(Base, UpdatableMixin):
    __tablename__ = "player_team_table"

    player_team_id: Mapped[str] = UUIDGenerator("player-team")

    player_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("players_table.player_id", ondelete="CASCADE"),
        nullable=False  
    )
    team_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("teams_table.team_id", ondelete="CASCADE"),
        nullable=False
    )

    is_team_captain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_accepted: Mapped[str] = mapped_column(
        player_is_accepted_enum,
        default="Pending",
        nullable=False
    )

    player_team_created_at: Mapped[datetime] = CreatedAt()
    player_team_updated_at: Mapped[datetime] = UpdatedAt()
    
    __table_args__ = (
        UniqueConstraint("player_id", "team_id", name="unique_player_team"),
    )

    player: Mapped["PlayerModel"] = relationship(
        "PlayerModel",
        back_populates="player_teams",
        lazy="joined"
    )

    team: Mapped["TeamModel"] = relationship(
        "TeamModel",
        back_populates="players",
        foreign_keys="[PlayerTeamModel.team_id]",
        lazy="joined"
    )
    
    def to_json(self) -> dict:
        return {
            **self.player.to_json(),
            'player_team_id': self.player_team_id,
            'team_id': self.team_id,
            'is_team_captain': self.is_team_captain,
            'is_accepted': self.is_accepted,
            'player_team_created_at': self.player_team_created_at.isoformat(),
            'player_team_updated_at': self.player_team_updated_at.isoformat()
        }
        
class LeaguePlayerModel(Base, UpdatableMixin):
    __tablename__ = "league_players_table"

    league_player_id: Mapped[str] = UUIDGenerator("league-player")
    
    league_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("leagues_table.league_id", ondelete="CASCADE"),
        nullable=False
    )

    league_category_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_categories_table.league_category_id", ondelete="CASCADE"),
        nullable=False
    )

    player_team_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("player_team_table.player_team_id", ondelete="CASCADE"),
        nullable=False
    )

    league_team_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("league_teams_table.league_team_id", ondelete="CASCADE"),
        nullable=True
    )

    total_points: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_ban_in_league: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_allowed_in_league: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    league_player_created_at: Mapped[datetime] = CreatedAt()
    league_player_updated_at: Mapped[datetime] = UpdatedAt()

    player_team: Mapped["PlayerTeamModel"] = relationship(
        "PlayerTeamModel",
        lazy="joined"
    )
    league_team: Mapped[Optional["LeagueTeamModel"]] = relationship(
        "LeagueTeamModel",
        back_populates="league_players",
        lazy="joined"
    )

    __table_args__ = (
        UniqueConstraint("league_id", "player_team_id", name="uq_league_player"),
        UniqueConstraint("league_team_id", "player_team_id", name="uq_league_team_player"),
        UniqueConstraint("league_category_id", "player_team_id", name="uq_league_category_player"),
    )
        
    def to_json(self) -> dict:
        return {
            'league_player_id': self.league_player_id,
            'league_id': self.league_id,
            'league_category_id': self.league_category_id,
            'league_team_id': self.league_team_id,
            'total_points': self.total_points,
            'is_ban_in_league': self.is_ban_in_league,
            'is_allowed_in_league': self.is_allowed_in_league,
            **self.player_team.to_json(),
            'league_player_created_at': self.league_player_created_at.isoformat(),
            'league_player_updated_at': self.league_player_updated_at.isoformat()
        }
    
_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]
