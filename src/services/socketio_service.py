import socketio
import redis.asyncio as aioredis
from src.utils.rate_limiter import socket_rate_limit, increment_limit

import socketio
from socketio.async_redis_manager import AsyncRedisManager
from src.config import Config

class SocketIOService:
    def __init__(self, redis_url: str = None):
        # allow CORS from your Flutter/web clients as needed; tighten for prod
        self.sio = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins='*',  # change to your domain in production
            client_manager=AsyncRedisManager(redis_url) if redis_url else None
        )

        # ASGI app will be mounted by the Quart app later
        self.app = socketio.ASGIApp(self.sio, static_files={})

        # register handlers
        self.register_handlers()

    def register_handlers(self):
        sio = self.sio

        @sio.event
        async def connect(sid, environ, auth):
            # auth can contain {"user_id": "...", "token": "..."} if needed
            print("socket connected:", sid, " auth:", auth)

        @sio.event
        async def disconnect(sid):
            print("socket disconnected:", sid)

        @sio.on('join')
        async def on_join(sid, data):
            """
            Client should emit: socket.emit('join', {'user_id': userId})
            or join entity rooms: {'entity_id': '...'}
            """
            user_id = data.get("user_id")
            entity_id = data.get("entity_id")
            if user_id:
                room = f"user:{user_id}"
                await sio.enter_room(sid, room)
                print(f"{sid} joined room {room}")
            if entity_id:
                room = f"entity:{entity_id}"
                await sio.enter_room(sid, room)
                print(f"{sid} joined room {room}")

        @sio.on('leave')
        async def on_leave(sid, data):
            user_id = data.get("user_id")
            if user_id:
                room = f"user:{user_id}"
                await sio.leave_room(sid, room)

        # Optionally allow sending messages via socket (if you want)
        @sio.on('send_message')
        async def on_send_message(sid, data):
            """
            If client wants to directly send via sockets, forward to your usual service.
            Example data: same payload as your REST route expects.
            Be careful with auth & validation.
            """
            # NOTE: you will need to call your MessageService here to persist & broadcast
            pass