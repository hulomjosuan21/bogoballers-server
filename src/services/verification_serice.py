import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from src.services.mailer_service import MailerService
from src.models.user import UserModel
from src.utils.api_response import ApiException


class VerificationService:
    TOKEN_EXPIRY_HOURS = 1

    @staticmethod
    def _generate_token() -> str:
        return secrets.token_urlsafe(32)

    async def send_verification_email(self, user_id: str, email: str, base_url: str, session: AsyncSession):
        result = await session.execute(
            select(UserModel).where(UserModel.user_id == user_id, UserModel.email == email)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ApiException("User not found", 404)

        token = self._generate_token()
        user.verification_token = token
        user.verification_token_created_at = datetime.now(timezone.utc)
        await session.commit()

        verify_link = f"{base_url}/verify?token={token}&user_id={user.user_id}"

        subject = "Verify your account"
        body = f"""
        Hi {user.email},

        Please verify your account by clicking the link below:
        {verify_link}

        This link will expire in {self.TOKEN_EXPIRY_HOURS} hour(s).
        """

        await MailerService.send_email(to=email, subject=subject, body=body)
        return {"message": "Verification email sent"}

    async def verify_user(self, token: str, user_id: str, session: AsyncSession):
        result = await session.execute(
            select(UserModel).where(UserModel.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user or not user.verification_token:
            raise ApiException("Invalid verification request", 400)

        if token != user.verification_token:
            raise ApiException("Invalid or expired token", 400)

        created_at = user.verification_token_created_at
        if not created_at or (datetime.now(timezone.utc) - created_at > timedelta(hours=self.TOKEN_EXPIRY_HOURS)):
            raise ApiException("Token expired", 400)

        user.is_verified = True
        user.verification_token = None
        user.verification_token_created_at = None
        await session.commit()

        return {"message": "User verified successfully"}

    async def resend_verification(self, user_id: str, email: str, base_url: str, session: AsyncSession):
        result = await session.execute(
            select(UserModel).where(UserModel.user_id == user_id, UserModel.email == email)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ApiException("User not found", 404)

        if user.is_verified:
            raise ApiException("User already verified", 400)

        # prevent spamming: allow resend only after 30 seconds
        if user.verification_token_created_at and (
            datetime.now(timezone.utc) - user.verification_token_created_at < timedelta(seconds=30)
        ):
            raise ApiException("Please wait before requesting another email", 429)

        return await self.send_verification_email(user_id, email, base_url, session)
