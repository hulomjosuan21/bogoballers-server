from quart import Blueprint, request
from quart_auth import login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.services.league.league_category_service import LeagueCategoryService
from src.utils.api_response import ApiException, ApiResponse

league_category_bp = Blueprint("league-category", __name__, url_prefix="/league/category")

service = LeagueCategoryService()

@league_category_bp.post("/<league_category_id>/round/<round_id>/update-format")
@login_required
async def update_round_format_route(league_category_id: str, round_id: str):
    try:
        data = await request.get_json()
        if not data or "round_format" not in data:
            raise ApiException("Missing format in request body")

        message, payload = await service.update_round_format(
            league_category_id, round_id, data["round_format"]
        )
        return await ApiResponse.success(message=message, payload=payload)
    except Exception as e:
        return await ApiResponse.error(e)

@league_category_bp.post("/<league_id>/add-category")
@login_required
async def add_league_category_route(league_id: str):
    try:
        category_ids = await request.get_json()
        result = await service.add_league_category(league_id, category_ids)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)

@league_category_bp.get("/<league_id>")
async def get_league_categories_route(league_id: str):
    try:
        result = await service.get_league_categories(league_id)
        return await ApiResponse.payload(result)
    except Exception as e:
        return await ApiResponse.error(e)

@league_category_bp.delete("/<league_category_id>")
async def delete_league_category_route(league_category_id: str):
    try:
        result = await service.delete_league_category(league_category_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)

@league_category_bp.put('/<league_category_id>')
async def update_league_category_route(league_category_id: str):
    try:
        data = await request.get_json()
        result = await service.update_league_category(league_category_id, data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)