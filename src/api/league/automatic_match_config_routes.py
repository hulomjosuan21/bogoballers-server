import traceback
from quart import Blueprint, request
from src.services.league.automatic_match_config_service import AutomaticMatchConfigService
from src.utils.api_response import ApiResponse

auto_match_config_bp = Blueprint('auto-match-config', __name__, url_prefix='/auto-match-config')
service = AutomaticMatchConfigService()

@auto_match_config_bp.get('/flow-state/<string:league_id>')
async def get_flow_state_route(league_id: str):
    try:
        state = await service.get_flow_state(league_id)
        return await ApiResponse.payload(state)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@auto_match_config_bp.post('/rounds')
async def create_round_route():
    try:
        data = await request.get_json()
        new_round = await service.create_round(
            league_category_id=data.get("league_category_id"),
            round_name=data.get("round_name"),
            round_order=data.get("round_order"),
            position=data.get("position"),
        )
        return await ApiResponse.payload(new_round)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@auto_match_config_bp.post('/formats')
async def create_or_attach_format_route():
    try:
        data = await request.get_json()
        saved = await service.create_or_attach_format(
            format_name=data.get("format_name"),
            round_id=data.get("round_id"),
            format_type=data.get("format_type"),
            position=data.get("position"),
        )
        return await ApiResponse.payload(saved)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@auto_match_config_bp.post('/edges')
async def create_edge_route():
    try:
        data = await request.get_json()
        saved = await service.create_edge(
            league_id=data.get("league_id"),
            league_category_id=data.get("league_category_id"),
            source_id=data.get("source"),
            target_id=data.get("target"),
            source_handle=data.get("sourceHandle"),
            target_handle=data.get("targetHandle"),
        )
        return await ApiResponse.payload(saved)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@auto_match_config_bp.delete('/edges/<string:edge_id>')
async def delete_edge_route(edge_id: str):
    try:
        ok = await service.delete_edge(edge_id)
        if ok:
            return await ApiResponse.success(message="Edge deleted.")
        return await ApiResponse.error("Edge not found.", status_code=404)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@auto_match_config_bp.put('/nodes/<string:node_type>/<string:node_id>/position')
async def update_node_position_route(node_type: str, node_id: str):
    try:
        data = await request.get_json()
        ok = await service.update_node_position(node_id, node_type, data.get("position"))
        if ok:
            return await ApiResponse.success(message="Position updated.")
        return await ApiResponse.error("Node not found.", status_code=404)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))
    
@auto_match_config_bp.delete('/nodes/<string:node_type>/<string:node_id>')
async def delete_node_route(node_type: str, node_id: str):
    try:
        ok = await service.delete_node(node_id, node_type)
        if ok:
            return await ApiResponse.success(message="Node deleted.")
        return await ApiResponse.error("Node not found.", status_code=404)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))
    
@auto_match_config_bp.patch('/nodes/format/<string:format_id>')
async def update_format(format_id: str):
    try:
        data = await request.get_json()
        format_name = data.get('format_name')
        format_obj = data.get('format_obj')
        ok = await service.update_format(format_id,format_name,format_obj)
        return await ApiResponse.success(message=ok)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)