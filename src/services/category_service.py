from sqlalchemy import select
from src.models.category import CategoryModel
from src.models.league_admin import LeagueAdministratorModel
from src.extensions import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import date, datetime
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
        
    async def create_one(self, league_administrator_id: str, data: dict):
        async with AsyncSession() as session:
            try:
                new_category = CategoryModel(
                    category_name=data.get("category_name"),
                    check_player_age=data.get("check_player_age", False),
                    player_min_age=data.get("player_min_age", None),
                    player_max_age=data.get("player_max_age", None),
                    check_address=data.get("check_address", False),
                    allowed_address=data.get("allowed_address", False),
                    allow_guest_team=data.get("allow_guest_team", False),
                    team_entrance_fee_amount=data.get("team_entrance_fee_amount", 0),
                    allow_guest_player=data.get("allow_guest_player", False),
                    guest_player_fee_amount=data.get("guest_player_fee_amount", 0),
                    player_gender=data.get("player_gender"),
                    requires_valid_document=data.get("requires_valid_document", False),
                    allowed_documents=data.get("allowed_documents", None),
                    document_valid_until=(
                        datetime.strptime(data["document_valid_until"], "%Y-%m-%d").date()
                        if data.get("document_valid_until") else None
                    ),
                    league_administrator_id=league_administrator_id
                )
                session.add(new_category)
                await session.commit()
                return "Category created successfully."
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e

    async def edit_one(self, category_id: str, data: dict):
        async with AsyncSession() as session:
            try:
                category = await session.get(CategoryModel, category_id)
                if not category:
                    raise ApiException("Category not found")

                if "document_valid_until" in data:
                    value = data["document_valid_until"]
                    if isinstance(value, str):
                        try:
                            data["document_valid_until"] = datetime.strptime(value, "%Y-%m-%d").date()
                        except ValueError:
                            data["document_valid_until"] = None
                    elif not isinstance(value, date):
                        data["document_valid_until"] = None

                category.copy_with(**data)

                await session.commit()
                return "Category updated successfully."
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e

    async def delete_one(self, category_id: str):
        async with AsyncSession() as session:
            try:
                category = await session.get(CategoryModel, category_id)
                if not category:
                    raise ApiException("Category not found")
                await session.delete(category)
                await session.commit()
                return "Category deleted successfully."
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e