import traceback
from quart import Blueprint, jsonify, make_response, request
from quart_auth import login_user, login_required, current_user, logout_user
from src.config import get_jwt_cookie_settings
from src.auth.auth_user import AuthUser
from src.utils.api_response import ApiResponse, ApiException
from src.utils.rate_limiter import rate_limit, login_limit
from src.services.league_admin_service import LeagueAdministratorService
from quart_jwt_extended import jwt_required, get_jwt_identity

league_admin_bp = Blueprint("league_admin", __name__, url_prefix="/league-administrator")

service = LeagueAdministratorService()

@league_admin_bp.get("/auth/jwt")
@jwt_required
async def get_jwt_route():
    try:
        claims = get_jwt_identity()
        return await ApiResponse.payload(claims)
    except Exception as e:
        return await ApiResponse.error(str(e))
    
@league_admin_bp.put('/update')
async def update_route():
    try:
        user_id = request.args.get('user_id') or current_user.auth_id
        data = await request.get_json()
        result = await service.update_one(user_id, data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)

@league_admin_bp.post("/login")
@rate_limit(login_limit)
async def login_route():
    try:
        form = await request.form
        email = form.get("email")
        password = form.get("password")

        if not email or not password:
            raise ApiException("Email and password are required")

        user, claims = await service.authenticate_login(email, password)
        
        login_user(AuthUser(user))
        cookie_settings = get_jwt_cookie_settings(claims)

        return await ApiResponse.success_with_cookie(
            message="Logged in successfully",
            cookies=cookie_settings
        )

    except Exception as e:
        return await ApiResponse.error(e)

@league_admin_bp.get("/auth")
@login_required
async def auth_route():
    try:
        user_id = current_user.auth_id
        payload = await service.get_authenticated_admin(user_id)
        return await ApiResponse.payload(payload)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_admin_bp.post("/logout")
@login_required
async def logout_route():
    logout_user()
    response = await make_response(jsonify({"message": "Logged out successfully"}), 200)
    response.delete_cookie("access_token") 
    response.delete_cookie("QUART_AUTH") 
    return response

@league_admin_bp.post("/register")
async def create_route():
    try:
        form = await request.form
        files = await request.files
        file = files.get("organization_logo")
        
        try:
            email = form["email"]
            password_str = form["password_str"]
            contact_number = form["contact_number"]
            organization_type = form["organization_type"]
            organization_name = form["organization_name"]
            organization_address = form["organization_address"]
            organization_logo_str = form.get("organization_logo")
        except KeyError as e:
             raise ApiException(f"Missing field: {str(e)}")

        result = await service.create_one(
            email=email,
            password_str=password_str,
            contact_number=contact_number,
            organization_type=organization_type,
            organization_name=organization_name,
            organization_address=organization_address,
            file=file,
            organization_logo_str=organization_logo_str
        )

        return await ApiResponse.success(
            message=result,
            status_code=201
        )
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_admin_bp.post('/send/notification')
async def send_notification_route():
    try:
        data = await request.get_json()
        title = data.get('title')
        message = data.get('message')
        image_url = data.get('image_url')
        from_id = data.get('from_id')
        to_id = data.get('to_id')
        
        result = await service.send_notification(title, message, from_id, to_id, image_url)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(str(e))