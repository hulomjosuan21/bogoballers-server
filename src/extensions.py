from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
import redis.asyncio as aioredis
from src.services.socketio_service import SocketIOService
from src.config import Config
from pathlib import Path
from argon2 import PasswordHasher
from contextlib import asynccontextmanager
from docxtpl import DocxTemplate
from firebase_admin import credentials, messaging
from asyncio import to_thread
import firebase_admin

Base = declarative_base()
ph = PasswordHasher()
engine = create_async_engine(Config.DATABASE_URL, echo=False, future=True)
AsyncSession = async_sessionmaker(engine, expire_on_commit=False)


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data" / "json"

TEMPLATE_PATH = BASE_DIR / "templates" / "league_template.docx"

tpl = DocxTemplate(TEMPLATE_PATH)

SERVICE_ACCOUNT_PATH = Path(__file__).parent.parent / "firebase.json"

redis_client = aioredis.from_url(Config.REDIS_URL, decode_responses=True)

@asynccontextmanager
async def db_session():
    async with AsyncSession() as session:
        yield session

socket_service = SocketIOService(redis_url="redis://127.0.0.1:6379")
sio = socket_service.sio 

cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred)

async def send_fcm_notification(token: str, title: str, body: str, data: dict):
    
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data,
        token=token
    )

    response = await to_thread(messaging.send, message)
    return response
