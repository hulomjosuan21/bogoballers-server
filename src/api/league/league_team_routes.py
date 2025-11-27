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
        traceback.print_exc()
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
                .team-info {{
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
                <p>Team <span class="team-info">{league_team.team_id}</span> has been registered.</p>
                <p>Payment Status: <span class="team-info">{league_team.payment_status}</span></p>
                <p>League Team ID: <span class="team-info">{league_team.league_team_id}</span></p>
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


@league_team_bp.get("/payment-result/cancel")
async def payment_cancel():
    try:
        league_team_id = request.args.get("league_team_id")
        league_team = await register_service.cancel_payment(league_team_id)
        if not league_team:
            return await ApiResponse.error("League team not found", 404)
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
                .team-info {{
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
                <p>Team <span class="team-info">{league_team.team.team_name}</span> payment was not completed.</p>
                <p>Payment Status: <span class="team-info">{league_team.payment_status}</span></p>
                <p>League Team ID: <span class="team-info">{league_team.league_team_id}</span></p>
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

@league_team_bp.patch("/submission/<league_team_id>")
async def update_league_team_route(league_team_id: str):
    try:
        data = await request.get_json()
        if not data:
            return await ApiResponse.error("Invalid JSON data in request.", 400)
            
        await register_service.update_league_team(league_team_id, data)
        return await ApiResponse.success(message="Team updated successfully")
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(f"An unexpected error occurred: {e}", 500)

@league_team_bp.delete("/submission/<league_team_id>")
async def remove_league_team_route(league_team_id: str):
    try:
        await register_service.remove_league_team(league_team_id)
        return await ApiResponse.success(message="Team removed successfully")
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(f"An unexpected error occurred: {e}", 500)

@league_team_bp.post("/submission/refund")
async def refund_route():
    try:
        data = await request.get_json()
        if not data:
            return await ApiResponse.error("Invalid JSON data in request.", 400)

        league_team_id = data.get("league_team_id")
        amount = data.get("amount")
        
        if not league_team_id or amount is None:
             return await ApiResponse.error("Missing required fields: league_team_id and amount.", 400)

        remove = data.get("remove", False) 

        await register_service.refund_payment(league_team_id, float(amount), remove, "requested_by_customer")
        return await ApiResponse.success(message="Refund processed successfully")
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(f"An unexpected error occurred: {e}", 500)

service = LeagueTeamService()

@league_team_bp.get("/all-checked/<league_category_id>")
async def get_all_with_elimination_check_route(league_category_id: str):
    try:
        teams = await service.get_all_with_elimination_check(league_category_id)
        return await ApiResponse.payload([team.to_json(include_schedule=True) for team in teams])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

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
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_team_bp.put('/update/<league_team_id>')
async def update_one_route(league_team_id: str):
    try:
        data = await request.get_json()
        result = await service.update_one(league_team_id=league_team_id,data=data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_team_bp.delete('/delete/<league_category_id>')
async def delete_one_route(league_team_id: str):
    try:
        result = await service.delete_one(league_team_id=league_team_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)    
    
@league_team_bp.get('/remaining-teams/<league_category_id>')
async def get_remaining(league_category_id: str):
    try:
        result = await service.get_remaining_teams(league_category_id=league_category_id)
        return await ApiResponse.payload([t.to_json() for t in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)    
    
@league_team_bp.get('/grouped/<league_category_id>')
async def get_grouped_teams(league_category_id: str):
    try:
        result = await service.get_grouped_teams(league_category_id=league_category_id)
        return await ApiResponse.payload([r.to_json() for r in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_team_bp.put('/update-grouped/<league_category_id>')
async def update_group_teams(league_category_id: str):
    try:
        data = await request.get_json()
        updates = data.get('teams', [])
        
        await service.update_group_teams(
            league_category_id=league_category_id, 
            group_updates=updates
        )
        
        result = await service.get_grouped_teams(league_category_id=league_category_id)
        return await ApiResponse.payload([r.to_json() for r in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)