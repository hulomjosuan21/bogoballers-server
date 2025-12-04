import traceback
from quart import Blueprint, request
from src.services.league.league_category_service import LeagueCategoryService
from src.utils.api_response import ApiResponse
from quart_auth import current_user
league_category_bp = Blueprint("league-category", __name__, url_prefix="/league-category")

service = LeagueCategoryService()

@league_category_bp.get('/metadata/<league_id>')
async def get_meta_data_route(league_id: str):
    try:
        result = await service.get_category_metadata(league_id)
        return await ApiResponse.payload(result)
    except Exception as e:
        return await ApiResponse.error(e) 
        

@league_category_bp.post("/all/<league_id>")
async def get_league_categories_route(league_id: str):
    try:
        data = await request.get_json()
        result = await service.get_many(league_id, data)
        return await ApiResponse.payload([c.to_json() for c in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_category_bp.delete("/<league_category_id>")
async def delete_league_category_route(league_category_id: str):
    try:
        result = await service.delet_one(league_category_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)

@league_category_bp.put('/<league_category_id>')
async def update_league_category_route(league_category_id: str):
    try:
        data = await request.get_json()
        result = await service.edit_one(league_category_id, data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)
    
@league_category_bp.put('/edit-many')
async def update_many_route():
    try:
        data = await request.get_json()
        result = await service.edit_many( data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)
    
@league_category_bp.get('/rounds-groups-names')
async def round_group_access():
    try:
        public_league_id = request.args.get('public_league_id')
        user_id = request.args.get('user_id') or current_user.auth_id
        result = await service.get_category_round_group_names(user_id=user_id, public_league_id=public_league_id)
        return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)