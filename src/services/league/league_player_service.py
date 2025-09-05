from sqlalchemy import select
from src.services.player_validator.player_no_team_validator import ValidateLeaguePlayer
from src.models.team import LeagueTeamModel, TeamModel
from src.models.player import LeaguePlayerModel, PlayerModel, PlayerTeamModel
from src.extensions import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload

from src.utils.api_response import ApiException

from src.services.team_validators.validate_league_team_entry import get_league_category_for_validation

class LeaguePlayerService:
    async def create_many(
        self,
        league_id: str,
        league_team_id: str,
        league_category_id: str,
        player_team_ids: list[str],
    ):
        try:
            async with AsyncSession() as session:
                league_players = [
                    LeaguePlayerModel(
                        league_id=league_id,
                        league_team_id=league_team_id,
                        player_team_id=player_team_id,
                        league_category_id=league_category_id
                    )
                    for player_team_id in player_team_ids
                ]

                session.add_all(league_players)
                await session.commit()
                return len(league_players)
        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise ApiException("Players is already registered for this league from other team", 409)
        
    async def get_many_loaded(self):
        return (
            select(LeaguePlayerModel)
            .options(
                # player_team -> player -> user
                selectinload(LeaguePlayerModel.player_team)
                .selectinload(PlayerTeamModel.player)
                .selectinload(PlayerModel.user),

                # player_team -> team -> user
                selectinload(LeaguePlayerModel.player_team)
                .selectinload(PlayerTeamModel.team)
                .selectinload(TeamModel.user),

                # league_team -> team -> user
                selectinload(LeaguePlayerModel.league_team)
                .selectinload(LeagueTeamModel.team)
                .selectinload(TeamModel.user),

                # other relationships
                selectinload(LeaguePlayerModel.league),
                selectinload(LeaguePlayerModel.league_category)
            )
        )
            
    async def get_all(self, league_id: str, league_category_id: str):
        async with AsyncSession() as session:
            stmt = await self.get_many_loaded()

            stmt = stmt.where(
                LeaguePlayerModel.league_id == league_id,
                LeaguePlayerModel.league_category_id == league_category_id
            )

            result = await session.execute(stmt)
            return result.scalars().all()
        
    async def create_one_no_team(
        self,
        league_id: str,
        league_category_id: str,
        player_id: str,
    ) -> str:
        async with AsyncSession() as session:
            try:
                # 1. Load player and league_category for validation
                player = await session.get(PlayerModel, player_id)
                if not player:
                    raise ApiException("Player not found", 404)

                league_category = await get_league_category_for_validation(
                    session=session, league_category_id=league_category_id
                )
                if not league_category:
                    raise ApiException("League category not found", 404)

                # 2. Run validation
                validator = ValidateLeaguePlayer(league_category, player)
                validator.validate()

                # 3. Create LeaguePlayer entry
                league_player = LeaguePlayerModel(
                    league_id=league_id,
                    league_category_id=league_category_id,
                    player_id=player_id,
                )

                session.add(league_player)
                await session.commit()
                await session.refresh(league_player)

                # 4. Reload with player+user for response
                stmt = (
                    select(LeaguePlayerModel)
                    .options(selectinload(LeaguePlayerModel.player).selectinload(PlayerModel.user))
                    .where(LeaguePlayerModel.league_player_id == league_player.league_player_id)
                )
                result = await session.execute(stmt)
                league_player_with_user = result.scalars().first()

                return f"Player {league_player_with_user.player.full_name} added to league with no team"

            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise ApiException(
                    "Player is already registered for this league or category", 409
                )
