import socketio
from src.services.redis_service import RedisService

class LiveMatchNamespace(socketio.AsyncNamespace):
    def __init__(self, namespace="/live"):
        super().__init__(namespace)
        self.redis_service = RedisService()

    async def on_join(self, sid, data):
        room = data.get("room")
        if room:
            await self.enter_room(sid, room)

    async def on_scorebook_update(self, sid, data):
        room = data.get("room")
        game_state = data.get("data")
        if room and game_state:
            await self.redis_service.set_state(room, game_state)
            await self.emit("scorebook_updated", game_state, to=room, skip_sid=sid)

    async def on_viewer_request_initial_state(self, sid, data):
        room = data.get("room")
        if room:
            latest_state = await self.redis_service.get_state(room)
            await self.emit("scorebook_initial_state", latest_state, to=sid)

    async def on_ping(self, sid, data):
        await self.emit('pong', data, to=sid)