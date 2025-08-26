from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from src.models.user import UserModel
    from src.models.team import TeamModel
    from src.models.league import LeagueTeamModel, LeagueModel
    
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Float, Integer, Date, ForeignKey, Enum as SqlEnum, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
import inspect
from datetime import date, datetime
from src.extensions import Base
from src.utils.db_utils import CreatedAt, UpdatedAt, UUIDGenerator
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

    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users_table.user_id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    full_name: Mapped[str] = mapped_column(String(250), nullable=False)
    gender: Mapped[str] = mapped_column(player_gender_enum, nullable=False)
    birth_date: Mapped[Date] = mapped_column(Date, nullable=False)
    player_address: Mapped[str] = mapped_column(String(250), nullable=False)

    jersey_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    jersey_number: Mapped[float] = mapped_column(Float, nullable=False)
    position: Mapped[List[str]] = mapped_column(JSONB, nullable=False)

    height_in: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    games_played: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    points_scored: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assists: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rebounds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    profile_image_url: Mapped[str] = mapped_column(Text, nullable=False)

    is_ban: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()
    
    player_teams: Mapped[List["PlayerTeamModel"]] = relationship(
        "PlayerTeamModel",
        back_populates="player"
    )
    user: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="player",
        cascade="all, delete",
        passive_deletes=True
    )
    
    def to_json_for_team(self):
        data = {
            "player_id": self.player_id,
            "user_id": self.user_id,
            "full_name": self.full_name,
            "gender": self.gender,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "player_address": self.player_address,
            "jersey_name": self.jersey_name,
            "jersey_number": self.jersey_number,
            "position": self.position,
            "height_in": self.height_in,
            "weight_kg": self.weight_kg,
            "games_played": self.games_played,
            "points_scored": self.points_scored,
            "assists": self.assists,
            "rebounds": self.rebounds,
            "profile_image_url": self.profile_image_url,
            "user": self.user.to_json(),
        }

        return data
    
    def to_json(self):
        data = {
            "player_id": self.player_id,
            "user_id": self.user_id,
            "full_name": self.full_name,
            "gender": self.gender,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "player_address": self.player_address,
            "jersey_name": self.jersey_name,
            "jersey_number": self.jersey_number,
            "position": self.position,
            "height_in": self.height_in,
            "weight_kg": self.weight_kg,
            "games_played": self.games_played,
            "points_scored": self.points_scored,
            "assists": self.assists,
            "rebounds": self.rebounds,
            "profile_image_url": self.profile_image_url,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "user": self.user.to_json(),
        }

        return data

player_is_accepted_enum = SqlEnum(
    "Pending",
    "Accepted",
    "Rejected",
    "Invited",
    name="player_is_accepted_enum",
    create_type=True,
)

class PlayerTeamModel(Base):
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

    is_ban: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_team_captain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_accepted: Mapped[str] = mapped_column(
        player_is_accepted_enum,
        default="Pending",
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint("player_id", "team_id", name="unique_player_team"),
    )

    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()
    

    player: Mapped["PlayerModel"] = relationship(
        "PlayerModel",
        back_populates="player_teams"
    )

    team: Mapped["TeamModel"] = relationship(
        "TeamModel",
        back_populates="players",
        foreign_keys="[PlayerTeamModel.team_id]"
    )

    def to_json_for_league(self):
        return {
            **self.player.to_json_for_team(),
            "team_id": self.team_id,
            "player_team_id": self.player_team_id,
        }

    def to_json_for_team(self):
        return {
            **self.player.to_json_for_team(),
            "team_id": self.team_id,
            "player_team_id": self.player_team_id,
            "is_ban": self.is_ban,
            "is_team_captain": self.is_team_captain,
            "is_accepted": self.is_accepted
        }
    
    def to_json(self):
        return {
            **self.player.to_json_for_team(),
            "player_team_id": self.player_team_id,
            "team_id": self.team_id,
            "is_ban": self.is_ban,
            "is_accepted": self.is_accepted,
            "is_team_captain": self.is_team_captain,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
class LeaguePlayerModel(Base):
    __tablename__ = "league_players_table"

    league_player_id: Mapped[str] = UUIDGenerator("league-player")
    
    league_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("leagues_table.league_id", ondelete="CASCADE"),
        nullable=False
    )

    # Optional link to PlayerTeamModel. Nullable to support players who join the league without being part of a team.
    player_team_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("player_team_table.player_team_id", ondelete="CASCADE"),
        nullable=True
    )

    # Optional link to LeagueTeamModel. Nullable to support unassigned players or future team assignments.
    league_team_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_teams_table.league_team_id", ondelete="CASCADE"),
        nullable=True
    )

    total_points: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_ban: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = CreatedAt()
    updated_at: Mapped[datetime] = UpdatedAt()

    player_team: Mapped["PlayerTeamModel"] = relationship("PlayerTeamModel")
    league_team: Mapped["LeagueTeamModel"] = relationship("LeagueTeamModel")
    
    league: Mapped["LeagueModel"] = relationship("LeagueModel")
    
_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]
