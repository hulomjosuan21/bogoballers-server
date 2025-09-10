from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from src.extensions import AsyncSession
from src.models.league import LeagueCategoryModel
from src.utils.api_response import ApiException

class LeagueCategoryService:
    async def get_league_categories(self, league_id: str):
        if not league_id:
            raise ApiException("No league id.")
        
        async with AsyncSession() as session:
            result = await session.execute(
                select(LeagueCategoryModel)
                .options(
                    joinedload(LeagueCategoryModel.rounds),
                )
                .where(LeagueCategoryModel.league_id == league_id)
            )

            categories = result.unique().scalars().all()
            return [c.to_json() for c in categories]

    async def delete_league_category(self, league_category_id: str):
        async with AsyncSession() as session:
            try:
                category = await session.get(LeagueCategoryModel, league_category_id)

                if not category:
                    raise ApiException("Category not found.", 404)

                await session.delete(category)
                await session.commit()
                
                return "Category deleted successfully"
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e 

    async def update_league_category(self, league_category_id: str, data: dict):
        async with AsyncSession() as session:
            try:
                category = await session.get(LeagueCategoryModel, league_category_id)
                if not category:
                    raise ApiException("Category not found", 404)
                
                category.copy_with(**data)
                await session.commit()
                
                return "Update success"
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e