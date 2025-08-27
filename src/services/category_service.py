from sqlalchemy import select
from src.models.league_admin import CategoryModel, LeagueAdministratorModel
from src.extensions import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.utils.api_response import ApiException

class CategoryService:
    async def get_all(self, user_id: str):
        async with AsyncSession() as session:
            result = await session.execute(
                select(LeagueAdministratorModel)
                .options(selectinload(LeagueAdministratorModel.categories))
                .where(LeagueAdministratorModel.user_id == user_id)
            )
            league_admin = result.scalar_one_or_none()
            return league_admin.categories_list() if league_admin else []

    async def get_one(self, category_id: str):
        async with AsyncSession() as session:
            category = await session.get(CategoryModel, category_id)
            if not category:
                raise ApiException("Category not found")
            return category

    async def create_one(self, league_administrator_id: str, data: dict):
        async with AsyncSession() as session:
            try:
                new_category = CategoryModel(**data, league_administrator_id=league_administrator_id)
                session.add(new_category)
                await session.commit()
                return "Category created successfully."
            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise

    async def update_one(self, category_id: str, data: dict):
        async with AsyncSession() as session:
            try:
                category = await session.get(CategoryModel, category_id)
                if not category:
                    raise ApiException("Category not found")
                category.copy_with(**data)
                await session.commit()
                return "Category updated successfully."
            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise

    async def delete_one(self, category_id: str):
        async with AsyncSession() as session:
            try:
                category = await session.get(CategoryModel, category_id)
                if not category:
                    raise ApiException("Category not found")
                await session.delete(category)
                await session.commit()
                return "Category deleted successfully."
            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise