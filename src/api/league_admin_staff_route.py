import traceback
from quart import Blueprint, jsonify, make_response, request
from quart_jwt_extended import create_access_token, decode_token
from quart_auth import login_required, current_user
from src.utils.api_response import ApiResponse, ApiException
from src.utils.rate_limiter import rate_limit, login_limit
from src.services.league_staff_service import LeagueStaffService
from quart_jwt_extended import jwt_required, get_jwt_identity

league_staff_bp = Blueprint("league_staff", __name__, url_prefix="/league-staff")

service = LeagueStaffService()

STAFF_COOKIE_KEY = "STAFF_ACCESS_TOKEN"

@league_staff_bp.post("/register/<league_administrator_id>")
@login_required
async def register_staff_route(league_administrator_id: str):
    try:
        data = await request.get_json()
        if not data.get("username") or not data.get("pin"):
            raise ApiException("Username and PIN are required", 400)

        if not league_administrator_id:
            raise ApiException("Current user is not a League Administrator", 403)
        await service.create_one(data, league_administrator_id)

        return await ApiResponse.success(
            message="Staff member created successfully",
            status_code=201
        )

    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_staff_bp.post("/login")
@rate_limit(login_limit)
async def login_route():
    try:
        form = await request.form
        username = form.get("username")
        
        pin = form.get("pin") 

        if not username or not pin:
            raise ApiException("Username and PIN are required", 400)

        staff, claims = await service.authenticate_login(username, pin)
        access_token = create_access_token(
            identity=str(staff.staff_id), 
            user_claims=claims 
        )

        response = await ApiResponse.success(
            message=f"Welcome back, {staff.username}",
        )

        response.set_cookie(
            key=STAFF_COOKIE_KEY,
            value=access_token,
            httponly=True,
            secure=False,
            samesite='Lax',
            max_age=3600 * 12
        )
        return response
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_staff_bp.post("/logout")
async def logout_route():
    response = await make_response(jsonify({"success": True, "message": "Logged out successfully"}), 200)
    
    response.delete_cookie(STAFF_COOKIE_KEY)
    
    return response

@league_staff_bp.get("/all/<league_administrator_id>")
@login_required
async def get_all_staff_route(league_administrator_id: str):
    try:
        if not league_administrator_id:
            return await ApiResponse.error("Admin not linked to a league", 403)

        staff_list = await service.get_all_by_admin(league_administrator_id)
        return await ApiResponse.payload(staff_list)

    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_staff_bp.put('/update/<staff_id>')
@login_required
async def update_staff_route(staff_id: str):
    try:
        data = await request.get_json()
        await service.update_one(staff_id, data)
        return await ApiResponse.success(
            message="Staff updated successfully",
        )
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_staff_bp.delete('/delete/<staff_id>')
@login_required
async def delete_staff_route(staff_id: str):
    try:
        await service.delete_one(staff_id)
        return await ApiResponse.success(
            message="Staff deleted successfully"
        )
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_staff_bp.get("/super-staff/status/<league_administrator_id>")
@login_required
async def check_super_staff_status(league_administrator_id: str):
    try:
        if not league_administrator_id:
             return await ApiResponse.error("Admin context missing", 403)
        status = await service.get_super_staff_status(league_administrator_id)
        
        return await ApiResponse.payload(status)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_staff_bp.post("/super-staff/create/<league_administrator_id>")
@login_required
async def create_super_staff_route(league_administrator_id: str):
    try:
        data = await request.get_json()
        staff, claims = await service.create_super_staff(data, league_administrator_id)
        access_token = create_access_token(
            identity=str(staff.staff_id), 
            user_claims=claims 
        )
        response = await ApiResponse.success(
            message="Super Staff created and logged in",
        )

        response.set_cookie(
            key=STAFF_COOKIE_KEY,
            value=access_token,
            httponly=True,
            secure=False,
            samesite='Lax',
            max_age=3600 * 12
        )
        
        return response
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_staff_bp.post("/super-staff/verify")
@login_required
async def verify_super_staff_route():
    try:
        data = await request.get_json()
        
        username = data.get("username")
        pin = data.get("pin")
        if not username or not pin:
             return await ApiResponse.error("Username and PIN required", 400)
        await service.verify_super_staff_credentials(
            username, 
            pin, 
        )
        return await ApiResponse.success("Credentials verified")
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    

@league_staff_bp.get("/me")
@jwt_required
async def get_current_staff_route():
    try:
        staff_id = get_jwt_identity()
        staff = await service.get_by_id(staff_id) 
        if not staff:
            return await ApiResponse.error("Staff member not found", 404)

        return await ApiResponse.payload({
                "staff_id": str(staff.staff_id),
                "username": staff.username,
                "role": staff.role_label,
                "permissions": staff.assigned_permissions
            })
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)