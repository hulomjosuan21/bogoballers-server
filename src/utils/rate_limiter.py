from functools import wraps
from quart import request
from src.limiter import limiter
from limits import RateLimitItemPerMinute, RateLimitItemPerSecond

login_limit = RateLimitItemPerMinute(10)
increment_limit = RateLimitItemPerSecond(1)

def rate_limit(limit):
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            allowed = await limiter.hit(limit, ip)
            if not allowed:
                from src.utils.api_response import ApiException
                raise ApiException("Too many requests, slow down!", 400)
            return await fn(*args, **kwargs)
        return wrapper
    return decorator

def socket_rate_limit(limit):
    def decorator(fn):
        @wraps(fn)
        async def wrapper(self, sid, data=None, *args, **kwargs):
            identity = (data.get("user_id") if isinstance(data, dict) else sid)
            allowed = await limiter.hit(limit, identity)
            if not allowed:
                await self.sio.emit("error", {"message": "Too many socket events, slow down!"}, to=sid)
                return
            return await fn(self, sid, data, *args, **kwargs)
        return wrapper
    return decorator
