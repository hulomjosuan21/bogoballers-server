from datetime import datetime, timezone
import secrets
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.services.mailer_service import MailerService
from src.extensions import AsyncSession
from src.models.user import UserModel
from src.utils.api_response import ApiException

class TeamManagerService:
    async def create_one(self, base_url: str, data: dict):
        async with AsyncSession() as session:
            try:
                email=data.get('email')
                display_name=data.get('display_name')
                
                new_user = UserModel(
                    email=email,
                    contact_number=data.get('contact_number'),
                    account_type="Team_Manager",
                    is_verified=False,
                    display_name=display_name,
                    fcm_token=data.get('fcm_token', None)
                )
                new_user.set_password(data.get('password_str'))
                
                token = secrets.token_urlsafe(32)
                new_user.verification_token = token
                new_user.verification_token_created_at = datetime.now(timezone.utc)
                
                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)
                
                verify_url = f"{base_url}/verification/verify-email?token={token}&uid={new_user.user_id}"
                
                subject = "Verify your Basketball League account"
                body = f"Hi {display_name},\n\nClick the link below to verify your account:\n{verify_url}\n\nThis link expires in 24 hours."
                await MailerService.send_email(to=email, subject=subject, body=body)
                
                return "Register successfully"
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e

    async def get_authenticated_user(self, user_id: str = None, current_user_id: str = None):
        async with AsyncSession() as session:
            if user_id:
                user = await session.get(UserModel, user_id)
            else:
                user = await session.get(UserModel, current_user_id)
            
            if not user:
                raise ApiException("No user found", 400)
            
            return user.to_json()