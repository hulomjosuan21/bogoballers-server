from datetime import datetime, timedelta, timezone
import jwt
from quart import Blueprint, request
from quart_auth import current_user, login_user, login_required
from sqlalchemy import select
from src.config import Config
from src.models.player import PlayerModel
from src.models.user import UserModel
from src.extensions import AsyncSession
from src.auth.auth_user import AuthUser
from src.utils.api_response import ApiResponse, ApiException

entity_bp = Blueprint("entity", __name__, url_prefix="/entity")

class EntityHandler:
    @staticmethod
    @entity_bp.post('/login')
    async def login():
        try:
            form = await request.form
            email = form.get("email")
            password = form.get("password")

            async with AsyncSession() as session:
                result = await session.execute(
                    select(UserModel).where(UserModel.email == email)
                )
                user = result.scalar_one_or_none()

                if not user or not user.verify_password(password):
                    raise ApiException("Invalid email or password")

                auth_user = AuthUser(user)
                login_user(auth_user)

                entity_id = user.user_id
                if user.account_type == "Player":
                    player_result = await session.execute(
                        select(PlayerModel).where(PlayerModel.user_id == user.user_id)
                    )
                    player = player_result.scalar_one_or_none()
                    if not player:
                        raise ApiException("Player record not found for this user",404)
                    entity_id = player.player_id
                elif user.account_type != "Team_Manager":
                    raise ApiException("Unauthorized account type")

                now = datetime.now(timezone.utc)
                exp = now + timedelta(weeks=1)

                payload = {
                    "sub": str(user.user_id),
                    "entity_id": str(entity_id),
                    "account_type": user.account_type,
                    "iat": int(now.timestamp()),
                    "exp": int(exp.timestamp())
                }

                access_token = jwt.encode(payload, Config.SECRET_KEY, algorithm=Config.ALGORITHM)

                if user.account_type == "Team_Manager":
                    return await ApiResponse.success(
                        redirect="/team-manager/main/screen",
                        payload=access_token
                    )

                elif user.account_type == "Player":
                    return await ApiResponse.success(
                        redirect="/player/main/screen",
                        payload=access_token
                    )
                raise ApiException("Unauthorized account type")
        except Exception as e:
            return await ApiResponse.error(e)

    @staticmethod
    @entity_bp.get("/auth")
    @login_required
    async def get_current_user():
        try:
            user_id = request.args.get("user_id")
            async with AsyncSession() as session:
                if user_id:
                    user = await session.get(UserModel, user_id)
                else:
                    user = await session.get(UserModel, current_user.auth_id)

                if not user:
                    raise ApiException("No user found",404)

                if user.account_type == "Team_Manager":
                    return await ApiResponse.payload('team_manager')

                elif user.account_type == "Player":
                    return await ApiResponse.payload('player')

                return await ApiResponse.error("Unauthorized account type",status_code=400)
        except Exception as e:
            return await ApiResponse.error(e)
        
    @staticmethod
    @entity_bp.post("/update-fcm")
    @login_required
    async def update_fcm():
        try:
            data = await request.get_json()
            fcm_token = data.get("fcm_token")

            if not fcm_token:
                raise ApiException("Missing FCM token")

            async with AsyncSession() as session:
                user = await session.get(UserModel, current_user.auth_id)
                if not user:
                    raise ApiException("User not found",404)

                if user.fcm_token != fcm_token:
                    user.fcm_token = fcm_token
                    session.add(user)
                    await session.commit()

            return await ApiResponse.success(message="FCM token updated")
        except Exception as e:
            return await ApiResponse.error(e)