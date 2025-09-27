import traceback
from quart import Blueprint, request
from src.extensions import AsyncSession
from src.services.verification_serice import VerificationService
from src.utils.api_response import ApiResponse, ApiException

verification_bp = Blueprint("verification", __name__, url_prefix="/verification")
service = VerificationService()


@verification_bp.post("/send")
async def send_verification():
    try:
        data = await request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")

        if not user_id or not email:
            raise ApiException("Missing user_id or email", 400)

        base_url = f"{request.scheme}://{request.host}"

        async with AsyncSession() as session:
            result = await service.send_verification_email(user_id, email, base_url, session)

        return await ApiResponse.success(data=result)

    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)


@verification_bp.get("/verify-email")
async def verify_user():
    try:
        token = request.args.get("token")
        user_id = request.args.get("uid")

        if not token or not user_id:
            raise ApiException("Missing token or user_id", 400)

        async with AsyncSession() as session:
            result = await service.verify_user(token, user_id, session)

        return await ApiResponse.success(payload=result)

    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)


@verification_bp.post("/resend")
async def resend_verification():
    try:
        data = await request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")

        if not user_id or not email:
            raise ApiException("Missing user_id or email", 400)

        base_url = f"{request.scheme}://{request.host}"

        async with AsyncSession() as session:
            result = await service.resend_verification(user_id, email, base_url, session)

        return await ApiResponse.success(data=result)

    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
