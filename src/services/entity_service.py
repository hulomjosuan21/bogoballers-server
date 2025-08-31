from quart_auth import login_user
from sqlalchemy import select
from src.config import Config
from src.models.player import PlayerModel
from src.models.user import UserModel
from src.extensions import AsyncSession
from src.auth.auth_user import AuthUser
from src.utils.api_response import ApiException
from datetime import datetime, timedelta, timezone
import jwt
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

class EntityService:
    async def seach_team_or_player(self, query: str):
        async with AsyncSession() as session:
            
            return {
                'result': 'the frontend must know what entity is found with query search',
                'payload': []
            }
    
    async def login(self, form):
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
                    raise ApiException("Player record not found for this user", 404)
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
            return {"user": user, "access_token": access_token}

    async def get_current_user(self, user_id=None, current_user=None):
        async with AsyncSession() as session:
            if user_id:
                user = await session.get(UserModel, user_id)
            else:
                user = await session.get(UserModel, current_user.auth_id)

            if not user:
                raise ApiException("No user found", 404)
            return user

    async def update_fcm(self, fcm_token, current_user):
        async with AsyncSession() as session:
            try:
                user = await session.get(UserModel, current_user.auth_id)
                if not user:
                    raise ApiException("User not found", 404)

                if user.fcm_token != fcm_token:
                    user.fcm_token = fcm_token
                    session.add(user)
                    await session.commit()
                return "FCM token updated"
            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise