from datetime import datetime, timezone
from quart import redirect, request, url_for, render_template, Blueprint, current_app
import aiosmtplib
from email.message import EmailMessage
from urllib.parse import quote, unquote, urlencode

from src.models.user import UserModel
from src.utils.token_utils import generate_verification_token, confirm_verification_token
from src.extensions import AsyncSession

async def send_verification_email(user, session, frontend_host: str | None = None):
    token = generate_verification_token(user.user_id)
    user.verification_token_created_at = datetime.now(timezone.utc)
    await session.flush()

    verify_backend_url = url_for("auth.verify_email", token=token, _external=True)
    if frontend_host:
        verify_url = f"{verify_backend_url}?frontend={quote(frontend_host)}"
    else:
        verify_url = verify_backend_url

    html_content = await render_template("email_verification.html", verify_url=verify_url)

    msg = EmailMessage()
    msg["From"] = current_app.config["MAIL_DEFAULT_SENDER"]
    msg["To"] = user.email
    msg["Subject"] = "Verify Your Email"
    msg.add_alternative(html_content, subtype="html")

    await aiosmtplib.send(
        msg,
        hostname=current_app.config["MAIL_SERVER"],
        port=current_app.config["MAIL_PORT"],
        username=current_app.config["MAIL_USERNAME"],
        password=current_app.config["MAIL_PASSWORD"],
        start_tls=current_app.config["MAIL_USE_TLS"]
    )

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

def _is_valid_frontend_host(url: str) -> bool:
    if not url:
        return False
    url = url.strip()
    return url.startswith("http://") or url.startswith("https://")

@auth_bp.get("/verify/<token>")
async def verify_email(token):
    frontend_host_enc = request.args.get("frontend")
    frontend_host = unquote(frontend_host_enc) if frontend_host_enc else None
    if frontend_host and not _is_valid_frontend_host(frontend_host):
        frontend_host = None

    def _redirect_to_frontend(status: str, msg: str | None = None):
        if frontend_host:
            params = {"verified": status}
            if msg:
                params["message"] = msg
            return redirect(f"{frontend_host.rstrip('/')}/auth/login?{urlencode(params)}")
        params = {"verified": status}
        if msg:
            params["message"] = msg
        return redirect(f"{request.host_url.rstrip('/')}/auth/login?{urlencode(params)}")

    user_id = confirm_verification_token(token, max_age=3600)
    if not user_id:
        return await render_template("verify_error.html")

    async with AsyncSession() as session:
        user = await session.get(UserModel, user_id)
        if not user:
            return await render_template("verify_error.html")

        if user.is_verified:
            return _redirect_to_frontend("already")

        if user.verification_token_created_at and \
           (datetime.now(timezone.utc) - user.verification_token_created_at).total_seconds() > 3600:
            return _redirect_to_frontend("expired")

        user.is_verified = True
        await session.commit()

    return _redirect_to_frontend("success")