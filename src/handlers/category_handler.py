from quart import Blueprint, request
from sqlalchemy import select

from src.models.league_admin import CategoryModel, LeagueAdministratorModel
from src.extensions import AsyncSession
from quart_auth import login_required, current_user
from src.utils.api_response import ApiException, ApiResponse
from sqlalchemy.orm import selectinload

category_bp = Blueprint('category',__name__,url_prefix='/category')

class CategoryHandler:
    @staticmethod
    @category_bp.get('/all')
    async def get_all_categories():
        try:
            user_id = request.args.get('user_id') or current_user.auth_id

            async with AsyncSession() as session:
                result = await session.execute(
                    select(LeagueAdministratorModel)
                    .options(selectinload(LeagueAdministratorModel.categories))
                    .where(LeagueAdministratorModel.user_id == user_id)
                )
                league_admin = result.scalar_one_or_none()
                
                if not league_admin:
                    return await ApiResponse.payload([])
                
                categories = league_admin.categories_list() 
                return await ApiResponse.payload(categories)

        except Exception as e:
            return await ApiResponse.error(e)

    @staticmethod
    @category_bp.get('/<category_id>')
    @login_required
    async def get_category(category_id: str):
        try:
            async with AsyncSession() as session:
                query = select(CategoryModel).where(CategoryModel.category_id == category_id)
                result = await session.execute(query)
                category = result.scalar_one_or_none()
                if not category:
                    raise ApiException("Category not found", 404)

                payload = category.to_json_league_category()
            return await ApiResponse.payload(payload)
        except Exception as e:
            return await ApiResponse.error(e)

    @staticmethod
    @category_bp.post('/<league_administrator_id>')
    @login_required
    async def create_category(league_administrator_id: str):
        try:
            data = await request.get_json()
            if not league_administrator_id:
                return await ApiResponse.error("league_administrator_id is required", 400)

            new_category = CategoryModel(
                league_administrator_id=league_administrator_id,
                category_name=data.get("category_name"),
                check_player_age=data.get("check_player_age"),
                player_min_age=data.get("player_min_age"),
                player_max_age=data.get("player_max_age"),
                player_gender=data.get("player_gender"),
                check_address=data.get("check_address"),
                allowed_address=data.get("allowed_address"),
                allow_guest_team=data.get("allow_guest_team"),
                team_entrance_fee_amount=data.get("team_entrance_fee_amount"),
                allow_guest_player=data.get("allow_guest_player"),
                guest_player_fee_amount=data.get("guest_player_fee_amount"),
            )

            async with AsyncSession() as session:
                session.add(new_category)
                await session.commit()

            return await ApiResponse.success(message="Created successfully.")
        except Exception as e:
            return await ApiResponse.error(e)

    @staticmethod
    @category_bp.put('/<category_id>')
    @login_required
    async def update_category(category_id: str):
        try:
            data = await request.get_json()
            async with AsyncSession() as session:
                query = select(CategoryModel).where(CategoryModel.category_id == category_id)
                result = await session.execute(query)
                category = result.scalar_one_or_none()

                if not category:
                    raise ApiException("Category not found", 404)

                category.copy_with(**data)

                await session.commit()
            return await ApiResponse.success(message="Update success.")
        except Exception as e:
            return await ApiResponse.error(e)

    @staticmethod
    @category_bp.delete('/<category_id>')
    @login_required
    async def delete_category(category_id: str):
        try:
            async with AsyncSession() as session:
                query = select(CategoryModel).where(CategoryModel.category_id == category_id)
                result = await session.execute(query)
                category = result.scalar_one_or_none()
                if not category:
                    raise ApiException("Category not found", 404)

                await session.delete(category)
                await session.commit()

            return await ApiResponse.success(message="Category deleted successfully")
        except Exception as e:
            return await ApiResponse.error(e)