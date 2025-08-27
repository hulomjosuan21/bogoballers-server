from quart import Blueprint, request, send_file
from quart_auth import login_required
from src.services.league.league_service import LeagueService
from src.utils.api_response import ApiResponse, ApiException

league_bp = Blueprint("league", __name__, url_prefix="/league")

service = LeagueService()

@league_bp.get("/<league_id>/export-pdf")
@login_required
async def export_league_pdf_route(league_id: str):
    try:
        buffer, league_title = await service.export_league_pdf(league_id)
        
        return await send_file(
            buffer,
            as_attachment=True,
            attachment_filename=f"{league_title}.pdf",
            mimetype="application/pdf"
        )
    except Exception as e:
        return await ApiResponse.error(e)

@league_bp.put("/<string:league_id>/option")
@login_required
async def update_league_option_route(league_id: str):
    try:
        data = await request.get_json()
        if not data or "option" not in data:
            raise ApiException("Missing 'option' in request body")

        option_updates = data["option"]
        result = await service.update_league_option(league_id, option_updates)
        return await ApiResponse.success(result)
    except Exception as e:
        return await ApiResponse.error(e)

@league_bp.post('/create-new')
@login_required
async def create_new_league_route():
    try:
        form = await request.form
        files = await request.files
        
        result = await service.create_new_league(form, files)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)

@league_bp.get("/active")
@login_required
async def get_active_route_route():
    try:
        resource_only = request.args.get("resource", "false").lower() == "true"
        result = await service.get_active(resource_only)
        return await ApiResponse.payload(result)
    except Exception as e:
        return await ApiResponse.error(e)

@league_bp.put("/<string:league_id>/update-field/<string:field_name>")
async def update_league_route(league_id: str, field_name: str):
    try:
        form = await request.form
        files = await request.files
        
        json_data = form.get(field_name)
        result = await service.update_league(league_id, field_name, json_data, files)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)