import traceback
from quart import Blueprint, request

from src.services.league.league_guest_service import LeagueGuestService
from src.utils.api_response import ApiResponse

league_guest_bp = Blueprint('guest-request-bp', __name__, url_prefix='/league-guest')
service = LeagueGuestService()

@league_guest_bp.post('/register')
async def register_guest_route():
    try:
        data = await request.get_json()
        result = await service.submit_guest_request(
            amount=data.get("amount"),
            league_category_id=data.get("league_category_id"),
            team_id=data.get("team_id"),
            player_id=data.get("player_id"),
            payment_method=data.get("payment_method"),
            success_url=f"https://api.bogoballers.site/league-guest/payment-result/success",
            cancel_url=f"https://api.bogoballers.site/league-guest/payment-result/cancel",
        )
        return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_guest_bp.get("/payment-result/success")
async def payment_success():
    try:
        guest_request_id = request.args.get("guest_request_id")
        guest_request = await service.confirm_guest_payment(guest_request_id)
        if not guest_request:
            return await ApiResponse.error("Guest request not found", 404)
        return await ApiResponse.payload({
            "message": "Payment completed for guest request.",
            "guest_request_id": guest_request.guest_request_id,
            "payment_status": guest_request.payment_status,
        })
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_guest_bp.get("/payment-result/cancel")
async def payment_cancel():
    try:
        guest_request_id = request.args.get("guest_request_id")
        guest_request = await service.cancel_guest_payment(guest_request_id)
        if not guest_request:
            return await ApiResponse.error("Guest request not found", 404)
        return await ApiResponse.payload({
            "message": "Payment cancelled for guest request.",
            "guest_request_id": guest_request.guest_request_id,
            "payment_status": guest_request.payment_status,
        })
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_guest_bp.patch("/submission/<string:guest_request_id>")
async def update_guest_request_route(guest_request_id: str):
    try:
        data = await request.get_json()
        if not data:
            return await ApiResponse.error("Invalid JSON data in request.", 400)
        
        updated_request = await service.update_guest_request(guest_request_id, data)
        return await ApiResponse.payload(updated_request.to_json())
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(f"An unexpected error occurred: {e}", 500)

@league_guest_bp.delete("/submission/<string:guest_request_id>")
async def remove_guest_request_route(guest_request_id: str):
    try:
        await service.remove_guest_request(guest_request_id)
        return await ApiResponse.success(message="Guest request removed successfully")
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(f"An unexpected error occurred: {e}", 500)

@league_guest_bp.post("/submission/refund")
async def refund_route():
    try:
        data = await request.get_json()
        if not data:
            return await ApiResponse.error("Invalid JSON data in request.", 400)

        guest_request_id = data.get("guest_request_id")
        amount = data.get("amount")
        if not guest_request_id or amount is None:
             return await ApiResponse.error("Missing required fields: guest_request_id and amount.", 400)

        remove = data.get("remove", False)
        result = await service.refund_guest_payment(guest_request_id, float(amount), remove, "requested_by_customer")
        return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(f"An unexpected error occurred: {e}", 500)

@league_guest_bp.get("/submissions/league/<league_category_id>")
async def get_requests_by_league(league_category_id: str):
    try:
        requests_list = await service.list_requests_by_league(league_category_id)
        return await ApiResponse.payload([r.to_json() for r in requests_list])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_guest_bp.get('/league-team/all/<league_category_id>')
async def get_league_team(league_category_id: str):
    try:
        result = await service.get_all_team(league_category_id=league_category_id)
        return await ApiResponse.payload([r.to_json() for r in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)