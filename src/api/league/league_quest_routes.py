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
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Payment Receipt</title>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    background-color: #f7f7f7;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    padding: 0;
                }}
                .receipt-container {{
                    background-color: #fff;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    width: 90%;
                    max-width: 400px;
                    text-align: center;
                }}
                .success-icon {{
                    font-size: 50px;
                    color: #4BB543;
                    margin-bottom: 10px;
                }}
                h1 {{
                    font-size: 24px;
                    margin-bottom: 10px;
                }}
                p {{
                    font-size: 16px;
                    margin: 5px 0;
                }}
                .info {{
                    font-weight: bold;
                    margin-top: 15px;
                }}
                .footer {{
                    margin-top: 20px;
                    font-size: 12px;
                    color: #999;
                }}
            </style>
        </head>
        <body>
            <div class="receipt-container">
                <div class="success-icon">✔️</div>
                <h1>Payment Successful!</h1>
                <p>Guest request ID: <span class="info">{guest_request.guest_request_id}</span></p>
                <p>Payment Status: <span class="info">{guest_request.payment_status}</span></p>
                <div class="footer">
                    Thank you for your payment.
                </div>
            </div>
        </body>
        </html>
        """

        return html_content
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
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Payment Cancelled</title>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    background-color: #f7f7f7;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    padding: 0;
                }}
                .receipt-container {{
                    background-color: #fff;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    width: 90%;
                    max-width: 400px;
                    text-align: center;
                }}
                .cancel-icon {{
                    font-size: 50px;
                    color: #FF4C4C;
                    margin-bottom: 10px;
                }}
                h1 {{
                    font-size: 24px;
                    margin-bottom: 10px;
                }}
                p {{
                    font-size: 16px;
                    margin: 5px 0;
                }}
                .info {{
                    font-weight: bold;
                    margin-top: 15px;
                }}
                .footer {{
                    margin-top: 20px;
                    font-size: 12px;
                    color: #999;
                }}
            </style>
        </head>
        <body>
            <div class="receipt-container">
                <div class="cancel-icon">❌</div>
                <h1>Payment Cancelled</h1>
                <p>Guest request ID: <span class="info">{guest_request.guest_request_id}</span></p>
                <p>Payment Status: <span class="info">{guest_request.payment_status}</span></p>
                <div class="footer">
                    Please try again or contact support.
                </div>
            </div>
        </body>
        </html>
        """

        return html_content
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
    
@league_guest_bp.get('/player/<league_id>')
async def fetch_guest_player_routes(league_id: str):
    try:
        result = await service.get_guest_players_as_serialized(league_id=league_id)
        return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_guest_bp.get('/team/<league_id>')
async def fetch_guest_team_routes(league_id: str):
    try:
        result = await service.get_guest_teams_as_serialized(league_id=league_id)
        return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)