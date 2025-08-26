from sqlite3 import IntegrityError
from quart import Blueprint, request
from quart_auth import login_required,current_user
from src.models.user import UserModel
from src.extensions import AsyncSession
from src.utils.api_response import ApiResponse, ApiException

team_mananger_bp = Blueprint('team-manager',__name__,url_prefix='/team-manager')

class TeamManagerHandler:
    @staticmethod
    @team_mananger_bp.post('/create')
    async def create():
        try:
            data = await request.get_json()

            email = data.get("email")
            password_str = data.get("password_str")
            contact_number = data.get("contact_number")
            display_name = data.get("display_name")

            if not email or not password_str or not contact_number or not display_name:
                raise ApiException("Missing required fields")


            async with AsyncSession() as session:
                new_user = UserModel(
                    email=email,
                    contact_number=contact_number,
                    account_type="Team_Manager",
                    is_verified=True,
                    display_name=display_name
                )
                new_user.set_password(password_str)

                session.add(new_user)
                
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()
                    raise ApiException("Email already exists",409)

            return await ApiResponse.success(message="Register successfully",status_code=201)
        except Exception as e:
            return await ApiResponse.error(e)
    
    @staticmethod
    @team_mananger_bp.get('/auth')
    @login_required
    async def auth():
        try:
            user_id = request.args.get("user_id")

            async with AsyncSession() as session:
                if user_id:
                    user = await session.get(UserModel, user_id)
                else:
                    user = await session.get(UserModel, current_user.auth_id)

                if not user:
                    return await ApiResponse.error("No user found",status_code=400)

                return await ApiResponse.payload(user.to_json_for_team_manager())

        except Exception as e:
            return await ApiResponse.error(e)