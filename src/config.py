import os
import secrets
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
import jwt
load_dotenv()

class Config:
    JWT_TOKEN_LOCATION = ["cookies"] 
    JWT_ACCESS_COOKIE_NAME = "STAFF_ACCESS_TOKEN" 
    JWT_COOKIE_CSRF_PROTECT = False

    AUTH_COOKIE_NAME = "access_token"
    DEBUG = True
    DATABASE_URL = os.getenv("DATABASE_URL")
    REDIS_URL = os.getenv("REDIS_URL")

    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", 5000))

    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
    SECURITY_PASSWORD_SALT = os.getenv("SECURITY_PASSWORD_SALT") or secrets.token_urlsafe(16)
    ALGORITHM = "HS256"

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or secrets.token_urlsafe(16)
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 604800))
    JWT_COOKIE_NAME = "access_token"
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_HTTPONLY = True
    JWT_COOKIE_SAMESITE = os.getenv("JWT_COOKIE_SAMESITE", "Lax")
    JWT_COOKIE_PATH = os.getenv("JWT_COOKIE_PATH", "/")
    JWT_COOKIE_DOMAIN = os.getenv("JWT_COOKIE_DOMAIN", None) or None
    
    QUART_AUTH_COOKIE_SECURE = False
    QUART_AUTH_COOKIE_HTTPONLY = True
    QUART_AUTH_COOKIE_SAMESITE = "Lax"

    CORS_ORIGINS = ["http://localhost:5173","https://bogoballers.site","https://basketball.bogoballers.site"]

    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() in ["true", "1", "yes"]
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")

    EMAIL_VERIFICATION_EXPIRATION = int(os.getenv("EMAIL_VERIFICATION_EXPIRATION", 3600))

def get_jwt_cookie_settings(claims: dict) -> dict:
    now = datetime.now(timezone.utc)

    payload = {
        **claims,
        "exp": now + timedelta(seconds=Config.JWT_ACCESS_TOKEN_EXPIRES),
        "iat": now,
    }

    access_token = jwt.encode(
        payload,
        Config.JWT_SECRET_KEY,
        algorithm=Config.JWT_ALGORITHM,
    )

    cookie = {
        Config.JWT_COOKIE_NAME: {
            "value": access_token,
            "httponly": Config.JWT_COOKIE_HTTPONLY,
            "secure": Config.JWT_COOKIE_SECURE,
            "samesite": Config.JWT_COOKIE_SAMESITE,
            "max-age": Config.JWT_ACCESS_TOKEN_EXPIRES,
            "path": Config.JWT_COOKIE_PATH,
        }
    }

    if Config.JWT_COOKIE_DOMAIN:
        cookie[Config.JWT_COOKIE_NAME]["domain"] = Config.JWT_COOKIE_DOMAIN

    return cookie