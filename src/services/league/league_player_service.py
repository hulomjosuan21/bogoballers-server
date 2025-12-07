from sqlalchemy import func, select
from src.services.player_validator.player_no_team_validator import ValidateLeaguePlayer
from src.models.team import LeagueTeamModel, TeamModel
from src.models.player import LeaguePlayerModel, PlayerModel, PlayerTeamModel
from src.extensions import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload, joinedload

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
            
    async def get_many(self, league_category_id: str, data: dict):
        async with AsyncSession() as session:
            conditions = [LeaguePlayerModel.league_category_id == league_category_id]
            
            if data:
                condition = data.get('condition')
                if condition == 'Accepted':
                    conditions.extend([
                        LeaguePlayerModel.is_ban_in_league.is_(False),
                        LeaguePlayerModel.is_allowed_in_league.is_(True)
                    ])
            
            stmt = (
                select(LeaguePlayerModel)
                .options(
                    joinedload(LeaguePlayerModel.league_team).joinedload(LeagueTeamModel.team)
                ).where(*conditions).order_by(LeaguePlayerModel.league_team_id)
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

    async def assign_player_to_team(self, league_team_id: str):
        async with AsyncSession() as session:
            ...
            
    async def update_one(self, league_player_id: str, condition: str):
        async with AsyncSession() as session:
            player = await session.get(LeaguePlayerModel, league_player_id)
            if not player:
                raise ApiException("League player not found", 404)

            if condition == "Include first 5":
                if not player.include_first5:  # only enforce when turning ON
                    stmt = (
                        select(func.count(LeaguePlayerModel.league_player_id))
                        .where(
                            LeaguePlayerModel.league_team_id == player.league_team_id,
                            LeaguePlayerModel.include_first5.is_(True),
                        )
                    )
                    result = await session.execute(stmt)
                    count = result.scalar_one()
                    if count >= 5:
                        raise ApiException("A team can only have 5 starters", 400)
                player.include_first5 = not player.include_first5

            # More conditions can go here...
            # elif condition == "Ban player": ...
            # elif condition == "Unban player": ...

            await session.commit()
            await session.refresh(player)
            return player.to_json()
        
    async def delete_one(self, league_player_id: str):
        async with AsyncSession() as session:
            player = await session.get(LeaguePlayerModel, league_player_id)
            if not player:
                raise ApiException("League player not found", 404)
            await session.delete(player)
            await session.commit()
            return "League player deleted successfully"