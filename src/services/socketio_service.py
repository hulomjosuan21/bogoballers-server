import socketio
import redis.asyncio as aioredis

class SocketIOService:
    def __init__(self, redis_url: str):
        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins="*"
        )

        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.redis_prefix = "connected_users:"

        self.sio.on("register")(self.register_user)
        self.sio.on("disconnect")(self.disconnect_user)
        self.sio.on("get_connected_devices")(self.get_connected_devices)

    async def register_user(self, sid, data):
        print(f"register_user called with sid={sid}, data={data}")
        user_id = data.get("user_id")
        if not user_id:
            await self.sio.emit("error", {"message": "Missing user_id"}, to=sid)
            return

        key = f"{self.redis_prefix}{user_id}"
        await self.redis.sadd(key, sid)
        await self.sio.emit("registered", {"message": "Registered successfully"}, to=sid)

    async def disconnect_user(self, sid):
        keys = await self.redis.keys(f"{self.redis_prefix}*")
        for key in keys:
            removed = await self.redis.srem(key, sid)
            if removed:
                break

    async def get_connected_devices(self, sid, data):
        user_id = data.get("user_id")
        if not user_id:
            await self.sio.emit("error", {"message": "Missing user_id"}, to=sid)
            return

        key = f"{self.redis_prefix}{user_id}"
        sids = await self.redis.smembers(key)
        await self.sio.emit("connected_devices", {"sids": list(sids)}, to=sid)
