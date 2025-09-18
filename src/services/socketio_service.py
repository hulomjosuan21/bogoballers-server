from datetime import time
import traceback
from urllib.parse import parse_qs
import socketio
from socketio.async_redis_manager import AsyncRedisManager

class SocketIOService:
    def __init__(self, redis_url: str = None):
        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins="*",
            client_manager=AsyncRedisManager(redis_url) if redis_url else None,
        )
        self.app = socketio.ASGIApp(self.sio, static_files={})
        self.message_service = None
        self.message_event = None
        self.live_match_namespace = None
        self.notification_service = None
        self.notification_event = None
        self.register_handlers()

    # Lazy load MessageService
    def _get_message_service(self):
        if self.message_service is None:
            from src.services.message_service import MessageService
            self.message_service = MessageService()
        return self.message_service

    def _get_live_match_namespace(self):
        if self.live_match_namespace is None:
            from src.namespaces.live_match_namespace import LiveMatchNamespace
            self.live_match_namespace = LiveMatchNamespace('/live')
            self.sio.register_namespace(self.live_match_namespace)
        return self.live_match_namespace

    # Lazy load MessageEvent
    def _get_message_event(self):
        from src.events.message_event import MessageEvent
        if self.message_event is None:
            self.message_event = MessageEvent(self.sio, self._get_message_service())
        return self.message_event

    # Lazy load NotificationService
    def _get_notification_service(self):
        if self.notification_service is None:
            from src.services.notification_service import NotificationService
            self.notification_service = NotificationService()
        return self.notification_service

    # Lazy load NotificationEvent
    def _get_notification_event(self):
        from src.events.notification_event import NotificationEvent
        if self.notification_event is None:
            self.notification_event = NotificationEvent(
                self.sio, self._get_notification_service()
            )
        return self.notification_event

    def register_handlers(self):
        sio = self.sio

        # 🔌 Register both event groups
        self._get_message_event()
        self._get_notification_event()
        
        self._get_live_match_namespace()

        # -------------------------
        # Core socket lifecycle
        # -------------------------
        @sio.event
        async def connect(sid, environ, auth):
            query_params = {}
            if "QUERY_STRING" in environ:
                query_params = parse_qs(environ["QUERY_STRING"])

            user_id = None
            if "user_id" in query_params:
                user_id = query_params["user_id"][0]
            elif auth and "user_id" in auth:
                user_id = auth["user_id"]

            if user_id:
                await sio.save_session(sid, {"user_id": user_id})

        @sio.event
        async def disconnect(sid):
            print(f"Socket disconnected: {sid}")

        @sio.on("ping")
        async def on_ping(sid, data):
            await sio.emit(
                "pong",
                {
                    "timestamp": time.time(),
                    "data": data,
                },
                room=sid,
            )

        # -------------------------
        # Room / User management
        # -------------------------
        @sio.on("join")
        async def on_join(sid, data):
            user_id = data.get("user_id")
            entity_id = data.get("entity_id")

            if user_id:
                room = f"user:{user_id}"
                await sio.enter_room(sid, room)
                session = await sio.get_session(sid)
                session["user_id"] = user_id
                await sio.save_session(sid, session)

            if entity_id:
                room = f"entity:{entity_id}"
                await sio.enter_room(sid, room)

        @sio.on("leave")
        async def on_leave(sid, data):
            user_id = data.get("user_id")
            entity_id = data.get("entity_id")

            if user_id:
                room = f"user:{user_id}"
                await sio.leave_room(sid, room)

            if entity_id:
                room = f"entity:{entity_id}"
                await sio.leave_room(sid, room)

        @sio.on("register")
        async def on_register(sid, data):
            user_id = data.get("user_id")
            if user_id:
                room = f"user:{user_id}"
                await sio.enter_room(sid, room)
                session = await sio.get_session(sid)
                session["user_id"] = user_id
                await sio.save_session(sid, session)
