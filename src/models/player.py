from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from src.models.user import UserModel
    from src.models.team import TeamModel
    from src.models.league import LeagueTeamModel
    from src.models.player_valid_documents import PlayerValidDocument
    
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Float, Integer, Date, ForeignKey, Enum as SqlEnum, Text, UniqueConstraint, case, cast
from sqlalchemy.dialects.postgresql import JSONB
import inspect
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import  datetime
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
    total_join_league: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_points_scored: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_assists: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_rebounds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    total_steals:        Mapped[int]   = mapped_column(Integer, default=0, nullable=False)
    total_blocks:        Mapped[int]   = mapped_column(Integer, default=0, nullable=False)
    total_turnovers:     Mapped[int]   = mapped_column(Integer, default=0, nullable=False)

    total_fg2_made:      Mapped[int]   = mapped_column(Integer, default=0, nullable=False)
    total_fg2_attempts:  Mapped[int]   = mapped_column(Integer, default=0, nullable=False)
    total_fg3_made:      Mapped[int]   = mapped_column(Integer, default=0, nullable=False)
    total_fg3_attempts:  Mapped[int]   = mapped_column(Integer, default=0, nullable=False)
    total_ft_made:       Mapped[int]   = mapped_column(Integer, default=0, nullable=False)
    total_ft_attempts:   Mapped[int]   = mapped_column(Integer, default=0, nullable=False)
    

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
    
    valid_documents: Mapped[List[PlayerValidDocument]] = relationship(
        "PlayerValidDocument",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
        
    @hybrid_property
    def platform_points(self) -> float:
        return (
            (self.total_points_scored * 1.0) # note: Core scoring ability: every point matters
            + (self.total_rebounds * 1.2) # note: Rebounds keep possessions alive & stop opponents’ chances
            + (self.total_assists * 1.5) # note: Playmaking is more than scoring — rewards teamwork
            + (self.total_steals * 3.0) # note: Steals create instant offense, rare & high impact
            + (self.total_blocks * 3.0) # note: Blocks shut down scoring attempts, game-changing plays
            - (self.total_turnovers * 2.0) # Turnovers hurt the team directly, punish heavily
            + ((self.total_fg2_made / max(self.total_fg2_attempts, 1)) * 10) # note: Reward 2PT shooting efficiency (smart scoring inside the arc)
            + ((self.total_fg3_made / max(self.total_fg3_attempts, 1)) * 15) # note: 3PTs are harder & more valuable, efficiency rewarded higher
            + ((self.total_ft_made / max(self.total_ft_attempts, 1)) * 5) # note: Free throw consistency = clutch factor, rewarded moderately
        )

    @platform_points.expression
    def platform_points(cls):
        return (
            (cls.total_points_scored * 1.0)
            + (cls.total_rebounds * 1.2)
            + (cls.total_assists * 1.5)
            + (cls.total_steals * 3.0)
            + (cls.total_blocks * 3.0)
            - (cls.total_turnovers * 2.0)
            + (
                (cls.total_fg2_made / case((cls.total_fg2_attempts > 0, cast(cls.total_fg2_attempts, Float)), else_=1.0))
                * 10
            )
            + (
                (cls.total_fg3_made / case((cls.total_fg3_attempts > 0, cast(cls.total_fg3_attempts, Float)), else_=1.0))
                * 15
            )
            + (
                (cls.total_ft_made / case((cls.total_ft_attempts > 0, cast(cls.total_ft_attempts, Float)), else_=1.0))
                * 5
            )
        )

    @hybrid_property
    def platform_points_per_game(self) -> float:
        return self.platform_points / max(self.total_games_played, 1)

    @platform_points_per_game.expression
    def platform_points_per_game(cls):
        return cls.platform_points / case((cls.total_games_played > 0, cast(cls.total_games_played, Float)), else_=1.0)
    
    @property
    def fg2_percentage_per_game(self) -> float:
        games = max(self.total_games_played, 1)
        attempts_pg = self.total_fg2_attempts / games
        made_pg = self.total_fg2_made / games
        return round((made_pg / max(attempts_pg, 1)) * 100, 2)

    @property
    def fg3_percentage_per_game(self) -> float:
        games = max(self.total_games_played, 1)
        attempts_pg = self.total_fg3_attempts / games
        made_pg = self.total_fg3_made / games
        return round((made_pg / max(attempts_pg, 1)) * 100, 2)

    @property
    def ft_percentage_per_game(self) -> float:
        games = max(self.total_games_played, 1)
        attempts_pg = self.total_ft_attempts / games
        made_pg = self.total_ft_made / games
        return round((made_pg / max(attempts_pg, 1)) * 100, 2)
    
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
            
            'total_steals': self.total_steals,
            'total_blocks': self.total_blocks,
            'total_turnovers': self.total_turnovers,

            'fg2_percentage_per_game': self.fg2_percentage_per_game,
            'fg3_percentage_per_game': self.fg3_percentage_per_game,
            'ft_percentage_per_game': self.ft_percentage_per_game,

            'platform_points': float(round(self.platform_points, 2)),
            'platform_points_per_game': float(round(self.platform_points_per_game, 2)),
            
            'total_join_league': self.total_join_league,
            'is_ban': self.is_ban,
            'is_allowed': self.is_allowed,
            'valid_documents': [d.to_json() for d in self.valid_documents] if self.valid_documents else [],
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
    
    include_first5: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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
            'league_team': self.league_team.to_json(include_players=False) if self.league_team else None,
            'is_ban_in_league': self.is_ban_in_league,
            'is_allowed_in_league': self.is_allowed_in_league,
            'include_first5': self.include_first5,
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
