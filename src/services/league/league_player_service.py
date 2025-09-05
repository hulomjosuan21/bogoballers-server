from sqlalchemy import and_, select
from src.models.player import LeaguePlayerModel, PlayerTeamModel
from src.extensions import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload

from src.utils.api_response import ApiException

class LeaguePlayerService:
    async def create_many(
        self,
        league_id: str,
        league_team_id: str,
        player_team_ids: list[str],
    ):
        try:
            async with AsyncSession() as session:
                league_players = [
                    LeaguePlayerModel(
                        league_id=league_id,
                        league_team_id=league_team_id,
                        player_team_id=player_team_id,
                    )
                    for player_team_id in player_team_ids
                ]

                session.add_all(league_players)
                await session.commit()
                return len(league_players)
        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise ApiException("Players is already registered for this league from other team", 409)
        
    async def get_many(self, session, *conditions, **filters):
        stmt = (
            select(LeaguePlayerModel)
            .options(
                selectinload(LeaguePlayerModel.player_team).selectinload(PlayerTeamModel.player),
                selectinload(LeaguePlayerModel.league_team),
                selectinload(LeaguePlayerModel.league),
            )
        )

        all_conditions = list(conditions)

        for field, value in filters.items():
            column = getattr(LeaguePlayerModel, field)
            all_conditions.append(column == value)

        if all_conditions:
            stmt = stmt.where(and_(*all_conditions))

        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_all(self, league_team_id: str):
        async with AsyncSession() as session:
            return await self.get_many(session, league_team_id=league_team_id)