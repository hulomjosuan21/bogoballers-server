import traceback
from quart import Blueprint, request, render_template
from src.services.league.league_team_service import LeagueTeamService
from src.utils.api_response import ApiResponse
from src.utils.server_utils import validate_required_fields
from src.utils.api_response import ApiException

league_team_bp = Blueprint('league-team', __name__, url_prefix="/league-team")
service = LeagueTeamService()

@league_team_bp.get('/all/<league_id>/<league_category_id>')
async def get_all_route(league_id: str, league_category_id: str):
    try:
        status = request.args.get('status', None)
        
        result = await service.get_all(status=status,league_id=league_id,league_category_id=league_category_id)
        return await ApiResponse.payload([t.to_json_for_match() for t in result])
    except Exception as e:
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


@league_team_bp.post('/register-team/free')
async def register_team_no_payment_route():
    try:
        data = await request.get_json()
        validate_required_fields(data, ["team_id", "league_id", "league_category_id"])
        
        result = await service.add_one_no_payment(data=data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)

@league_team_bp.post('/register-team')
async def register_team_route():
    try:
        data = await request.get_json()
        validate_required_fields(data, ["team_id", "league_id", "league_category_id", "payment_method"])
        
        if await service.check_entry_one(data=data):
            result = await service.add_one(data=data)

        if "checkout_url" in result:
            return await ApiResponse.success(
                message=result["message"],
                payload={
                    "checkout_url": result["checkout_url"],
                    "payment_intent_id": result["payment_intent_id"],
                    "league_team_id": result["league_team_id"],
                    "requires_payment": True,
                    "amount": result.get("amount")
                }
            )
        return await ApiResponse.success(
            message=result["message"],
            payload={
                "league_team_id": result.get("league_team_id"),
                "amount_paid": result.get("amount_paid")
            }
        )
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_team_bp.post('/update-payment-status')
async def update_payment_status_route():
    data = await request.get_json()
    validate_required_fields(data, ["payment_intent_id"])
    result = await service.confirm_payment_and_update_status(data["payment_intent_id"])
    return await ApiResponse.success(
        message=result["message"],
        payload={
            "league_team_id": result.get("league_team_id"),
            "payment_updated": True,
            "amount_paid": result.get("amount_paid")
        }
    )

@league_team_bp.post('/confirm-payment')
async def confirm_payment_route():
    data = await request.get_json()
    validate_required_fields(data, ["payment_intent_id"])
    result = await service.confirm_payment_and_register(data["payment_intent_id"])
    return await ApiResponse.success(
        message=result["message"],
        payload={
            "league_team_id": result.get("league_team_id"),
            "registration_complete": True,
            "amount_paid": result.get("amount_paid")
        }
    )

@league_team_bp.get('/payment-webhook')
async def payment_webhook_get():
    return await ApiResponse.success(message="PayMongo webhook endpoint is active")

@league_team_bp.post('/payment-webhook')
async def payment_webhook_post():
    data = await request.get_json()
    event_type = data.get("data", {}).get("attributes", {}).get("type")

    if event_type == "payment_intent.succeeded":
        payment_intent_id = data.get("data", {}).get("attributes", {}).get("data", {}).get("id")
        if not payment_intent_id:
            raise ApiException("Payment intent ID not found in webhook data", 400)
        result = await service.confirm_payment_and_update_status(payment_intent_id)
        return await ApiResponse.success(
            message="Payment status updated successfully",
            payload={"event_processed": True, "status_updated": True, "league_team_id": result.get("league_team_id")}
        )

    if event_type == "payment_intent.payment_failed":
        return await ApiResponse.success(
            message="Payment failure event received",
            payload={"event_processed": True, "payment_failed": True}
        )

    return await ApiResponse.success(
        message=f"Webhook event '{event_type}' received but not processed",
        payload={"event_processed": False, "event_type": event_type}
    )

@league_team_bp.get('/payment-success')
async def payment_success():
    try:
        payment_intent_id = request.args.get("payment_intent_id")
        league_team_id = request.args.get("league_team_id")

        if payment_intent_id:
            await service.update_one(league_team_id=league_team_id,data={"payment_status": "Paid Online"})

        return await render_template("payment_success.html")
    except:
        return await render_template("payment_error.html")


@league_team_bp.get('/payment-cancel')
async def payment_cancel():
    try:
        league_team_id = request.args.get("league_team_id")
        if not league_team_id:
            return
        
        await service.delete_one(league_team_id=league_team_id)
        return await render_template("payment_cancel.html")
    except:
        return await render_template("payment_error.html")

@league_team_bp.get('/payment-error')
async def payment_error():
    return await render_template("payment_error.html")
