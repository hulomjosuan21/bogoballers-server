from quart import Blueprint, jsonify, make_response, request
from quart_auth import login_user, login_required, current_user, logout_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from src.models.notification import NotificationModel
from src.logging.log_entity_action import log_action
from src.config import get_jwt_cookie_settings
from src.auth.auth_user import AuthUser
from src.services.cloudinary_service import CloudinaryService
from src.extensions import AsyncSession
from src.models.league_admin import LeagueAdministratorModel
from src.models.user import UserModel
from src.utils.api_response import ApiResponse, ApiException
import traceback
from datetime import datetime, timezone


league_admin_bp = Blueprint("league_admin", __name__, url_prefix="/league-administrator")

class LeagueAdministratorHandler:
    @staticmethod
    @league_admin_bp.post("/login")
    @log_action(
        model_class=LeagueAdministratorModel,
        match_column=LeagueAdministratorModel.user_id,
        action_message="Logged in"
    )
    async def login_league_administrator():
        try:
            form = await request.form
            email = form.get("email")
            password = form.get("password")

            if not email or not password:
                raise ApiException("Email and password are required")

            async with AsyncSession() as async_session:
                result = await async_session.execute(select(UserModel).where(UserModel.email == email))
                user = result.scalar_one_or_none()

                if not user or not user.verify_password(password):
                    raise ApiException("Invalid credentials",401)

                login_user(AuthUser(user))

                league_admin_id = None
                if user.account_type in ("League_Administrator_Local", "League_Administrator_LGU"):
                    result = await async_session.execute(
                        select(LeagueAdministratorModel).where(LeagueAdministratorModel.user_id == user.user_id)
                    )
                    league_admin = result.scalar_one_or_none()
                    if league_admin:
                        league_admin_id = league_admin.league_administrator_id

                claims = {
                    "sub": str(user.user_id),
                    "email": user.email,
                    "account_type": user.account_type,
                    "league_administrator_id": league_admin_id,
                    "is_verified": user.is_verified
                }

                cookie_settings = get_jwt_cookie_settings(claims)

                return await ApiResponse.success_with_cookie(
                    message="Logged in successfully",
                    cookies=cookie_settings
                )

        except Exception as e:
            return await ApiResponse.error(e)

    @staticmethod
    @league_admin_bp.get("/auth")
    @login_required
    async def get_league_administrator_profile():
        try:
            user_id = current_user.auth_id

            async with AsyncSession() as async_session:
                league_admin_result = (
                    select(LeagueAdministratorModel)
                    .options(joinedload(LeagueAdministratorModel.user))
                    .where(LeagueAdministratorModel.user_id == user_id)
                )
                result = await async_session.execute(league_admin_result)
                league_admin = result.scalar_one_or_none()

                if not league_admin:
                    raise ApiException("League Administrator not found",404)

                if league_admin.user.account_type not in (
                    "League_Administrator_Local",
                    "League_Administrator_LGU",
                ):
                    raise ApiException("Not a League Administrator",403)

                payload = league_admin.to_json()

            return await ApiResponse.payload(payload)

        except Exception as e:
            return await ApiResponse.error(e)

    @staticmethod
    @league_admin_bp.post("/logout")
    @login_required
    async def logout():
        logout_user()
        response = await make_response(jsonify({"message": "Logged out successfully"}), 200)
        response.delete_cookie("access_token") 
        response.delete_cookie("QUART_AUTH") 
        return response
        
    @staticmethod
    @league_admin_bp.post("/register")
    async def create_league_administrator():
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

            user = UserModel(
                email=email,
                contact_number=contact_number,
                account_type="League_Administrator_Local",
                verification_token_created_at=datetime.now(timezone.utc),
                is_verified=True
            )
            user.set_password(password_str)
            async with AsyncSession() as async_session:
                async_session.add(user)
                await async_session.flush()

                league_admin = LeagueAdministratorModel(
                    user_id=user.user_id,
                    organization_type=organization_type,
                    organization_name=organization_name,
                    organization_address=organization_address,
                    organization_logo_url=None
                )
                async_session.add(league_admin)
                await async_session.commit()

            organization_logo_url = None

            if file:
                try:
                    organization_logo_url = await CloudinaryService.upload_file(
                        file=file,
                        folder="league-admin/organization-logos"
                    )
                except Exception as e:
                    raise ApiException("⚠ Logo upload failed")

            elif organization_logo_str and organization_logo_str.strip():
                organization_logo_url = organization_logo_str.strip()

            if organization_logo_url:
                async with AsyncSession() as async_session:
                    result = await async_session.get(LeagueAdministratorModel, league_admin.league_administrator_id)
                    if result:
                        result.organization_logo_url = organization_logo_url
                        await async_session.commit()

            frontend_host = request.headers.get("Origin") or form.get("frontend_url")

            # try:
            #     async with AsyncSession() as async_session:
            #         await send_verification_email(user, async_session, frontend_host=frontend_host)
            # except Exception:
            #     pass

            return await ApiResponse.success(
                message="League Administrator registered successfully. Please check your email for verification.",
                status_code=201
            )

        except IntegrityError:
            return await ApiResponse.error(
                "Email already registered or league admin already exists.",
                status_code=409
            )
        except Exception as e:
            return await ApiResponse.error(e)

    @staticmethod
    @league_admin_bp.post('/send/notification')
    async def send_notification():
        data = await request.get_json()
        title = data.get('title')
        message = data.get('message')
        image_url = data.get('image_url')
        from_id = data.get('from_id')
        to_id = data.get('to_id')
        
        async with AsyncSession() as session:
            try:
                user = await session.get(UserModel, to_id)
                new_notification = NotificationModel(
                    title=title,
                    message=message,
                    image_url=image_url,
                    from_id=from_id,
                    to_id=to_id
                )
                
                await new_notification.send(token=user.fcm_token)
                session.add(new_notification)
                await session.commit()
                
                return await ApiResponse.success()
            except Exception as e:
                await session.rollback()
                traceback.print_exc()
                return await ApiResponse.error(str(e))