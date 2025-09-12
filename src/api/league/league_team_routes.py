import traceback
from quart import Blueprint, request
from src.services.league.register_league_team_service import RegisterLeagueService
from src.services.league.league_team_service import LeagueTeamService
from src.utils.api_response import ApiResponse
from src.utils.server_utils import get_bool_arg

league_team_bp = Blueprint("league-team", __name__, url_prefix="/league-team")
register_service = RegisterLeagueService()

@league_team_bp.post("/register")
async def register_team_route():
    try:
        data = await request.get_json()

        result = await register_service.register_team_request(
            team_id=data["team_id"],
            league_id=data["league_id"],
            league_category_id=data["league_category_id"],
            amount=data.get("amount"),
            payment_method=data["payment_method"],
            success_url=f"https://api.bogoballers.site/league-team/payment-result/success",
            cancel_url=f"https://api.bogoballers.site/league-team/payment-result/cancel",
        )
        return await ApiResponse.payload(result)
    except Exception as e:
        return await ApiResponse.error(e)


@league_team_bp.get("/payment-result/success")
async def payment_success():
    try:
        league_team_id = request.args.get("league_team_id")
        league_team = await register_service.confirm_payment_and_register(
            league_team_id
        )
        if not league_team:
            return await ApiResponse.error("League team not found", 404)
        return await ApiResponse.payload(
            {
                "message": f"Payment completed. Team {league_team.team_id} registered.",
                "league_team_id": league_team.league_team_id,
                "payment_status": league_team.payment_status,
            }
        )
    except Exception as e:
        return await ApiResponse.error(e)


@league_team_bp.get("/payment-result/cancel")
async def payment_cancel():
    try:
        league_team_id = request.args.get("league_team_id")
        league_team = await register_service.cancel_payment(league_team_id)
        if not league_team:
            return await ApiResponse.error("League team not found", 404)
        return await ApiResponse.payload(
            {
                "message": f"Payment cancelled for team {league_team.team_id}.",
                "league_team_id": league_team.league_team_id,
                "payment_status": league_team.payment_status,
            }
        )
    except Exception as e:
        return await ApiResponse.error(e)

@league_team_bp.post("/refund")
async def refund_route():
    try:
        data = await request.get_json()
        league_team_id = data["league_team_id"]
        amount = data["amount"]
        reason = data.get("reason", "requested_by_customer")
        payment_status = data.get("payment_status","Pending")
        remove = get_bool_arg(request,'remove')

        refund = await register_service.refund_payment(league_team_id, amount, payment_status, remove, reason)
        if not refund:
            return await ApiResponse.error("League team not found or refund failed", 404)

        msg = f"Refund successfully refundId: {refund["data"]["id"]}"
        return await ApiResponse.success(message=msg)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

service = LeagueTeamService()

@league_team_bp.post('/all/<league_category_id>')
async def get_all_route(league_category_id: str):
    try:
        data = await request.get_json()
        result = await service.get_all(league_category_id, data)
        return await ApiResponse.payload([t.to_json() for t in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_team_bp.put('/validate-entry/<league_id>/<league_category_id>/<league_team_id>')
async def validate_team_entry_route(league_id: str, league_category_id: str, league_team_id: str):
    try:
        result = await service.validate_team_entry(league_id=league_id, league_category_id=league_category_id,league_team_id=league_team_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_team_bp.get('/all/submission/<league_id>/<league_category_id>')
async def get_teams_route(league_id: str, league_category_id: str):
    try:
        result = await service.get_all_submission(
                                       league_id=league_id,
                                       league_category_id=league_category_id
                                    )
        return await ApiResponse.payload([t.to_json() for t in result])
    except Exception as e:
        return await ApiResponse.error(e)
    
@league_team_bp.put('/update/<league_team_id>')
async def update_one_route(league_team_id: str):
    try:
        data = await request.get_json()
        result = await service.update_one(league_team_id=league_team_id,data=data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)
    
@league_team_bp.delete('/delete/<league_team_id>')
async def delete_one_route(league_team_id: str):
    try:
        result = await service.delete_one(league_team_id=league_team_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)    
    