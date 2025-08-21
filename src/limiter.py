from limits.aio.storage import RedisStorage
from limits.aio.strategies import FixedWindowRateLimiter
from src.config import Config

limiter_storage = RedisStorage(Config.REDIS_URL)
limiter = FixedWindowRateLimiter(limiter_storage)