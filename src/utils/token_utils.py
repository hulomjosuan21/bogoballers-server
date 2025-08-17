from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from quart import current_app

def generate_verification_token(user_id: str) -> str:
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return s.dumps(user_id, salt=current_app.config["SECURITY_PASSWORD_SALT"])

def confirm_verification_token(token: str, max_age: int = 3600) -> str | None:
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        return s.loads(token, salt=current_app.config["SECURITY_PASSWORD_SALT"], max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None
