import socketio
from src.services.redis_service import RedisService

class LiveMatchNamespace(socketio.AsyncNamespace):
    def __init__(self, namespace="/live"):
        super().__init__(namespace)
        self.redis_service = RedisService()

    def on_connect(self, sid, environ):
        print(f"Client connected: {sid}")

    def on_disconnect(self, sid):
        print(f"Client disconnected: {sid}")

    async def on_join(self, sid, data):
        room = data.get("room")
        if room:
            await self.enter_room(sid, room)
            print(f"Client {sid} joined room: {room}")

    async def on_scorebook_update(self, sid, data):
        room = data.get("room")
        game_state = data.get("data")
        if room and game_state:
            await self.redis_service.set_state(room, game_state)
            await self.emit("scorebook_updated", game_state, to=room, skip_sid=sid)
            print(f"Update for {room} stored and broadcasted.")

    async def on_viewer_request_initial_state(self, sid, data):
        room = data.get("room")
        if room:
            latest_state = await self.redis_service.get_state(room)
            await self.emit("scorebook_initial_state", latest_state, to=sid)
            print(f"Sent initial state for {room} to client {sid}")
