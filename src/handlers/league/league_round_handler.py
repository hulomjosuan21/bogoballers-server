from quart import Blueprint, request
from sqlalchemy.exc import IntegrityError,SQLAlchemyError

from src.models.league import LeagueCategoryRoundModel
from src.extensions import AsyncSession
from src.utils.api_response import ApiException, ApiResponse
round_bp = Blueprint('round',__name__,url_prefix="/league/round")

class LeagueRoundHandler:
    @staticmethod
    @round_bp.put('/<round_id>')
    async def update(round_id: str):
        try:
            data = await request.get_json()
            async with AsyncSession() as session:
                category_round = await session.get(LeagueCategoryRoundModel, round_id)
                if not category_round:
                    raise ApiException("No category round found")
                category_round.copy_with(**data)
                await session.commit()
            return await ApiResponse.success(message="Update success.")
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            return await ApiResponse.error(f"Error: {str(e)}")
        except Exception as e:
            return await ApiResponse.error(e)