from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.models.league import LeagueCategoryRoundModel
from src.extensions import AsyncSession
from src.utils.api_response import ApiException

class LeagueRoundService:
    async def update_one(self, round_id: str, data: dict):
        try:
            async with AsyncSession() as session:
                category_round = await session.get(LeagueCategoryRoundModel, round_id)
                if not category_round:
                    raise ApiException("No category round found")
                
                category_round.copy_with(**data)
                await session.commit()
                
            return "Round config successfully."
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e 