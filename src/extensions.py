from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
import redis.asyncio as aioredis
from src.services.socketio_service import SocketIOService
from src.config import Config
from pathlib import Path
from argon2 import PasswordHasher
from contextlib import asynccontextmanager
import firebase_admin
from firebase_admin import credentials, messaging
import json

Base = declarative_base()
ph = PasswordHasher()
engine = create_async_engine(Config.DATABASE_URL, echo=False, future=True)
AsyncSession = async_sessionmaker(engine, expire_on_commit=False)

BASE_DIR = Path(__file__).resolve().parent

def path_in(*parts):
    return BASE_DIR.joinpath(*parts)

DATA_DIR = path_in("data", "json")
TEMPLATE_PATH = path_in("templates", "league_template.docx")

SERVICE_ACCOUNT_PATH = Path(__file__).parent.parent / "firebase.json"
redis_client = aioredis.from_url(Config.REDIS_URL, decode_responses=True)

SETTINGS_PATH = BASE_DIR.parent / "settings.json"
with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
    settings = json.load(f)
    
@asynccontextmanager
async def db_session():
    async with AsyncSession() as session:
        yield session

socket_service = SocketIOService(redis_url=Config.REDIS_URL)
sio = socket_service.sio 

cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred)
