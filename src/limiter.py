from limits import RateLimitItem
from limits.aio.storage import RedisStorage
from limits.aio.strategies import FixedWindowRateLimiter
from quart import Request
from src.config import Config
from src.utils.api_response import ApiException

limiter_storage = RedisStorage(Config.REDIS_URL)
limiter = FixedWindowRateLimiter(limiter_storage)

async def enforce_rate_limit(req: Request, limit: RateLimitItem, key_prefix: str = "global"):
    client_id = req.remote_addr or "anonymous"
    key = f"{key_prefix}:{client_id}"

    allowed = await limiter.hit(limit, key)
    if not allowed:
        raise ApiException("Too many requests, slow down! Try again later.", 429)