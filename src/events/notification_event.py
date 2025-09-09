import socketio
import traceback
import time
from src.services.notification_service import NotificationService

class NotificationEvent:
    def __init__(self, sio: socketio.AsyncServer, notification_service: NotificationService):
        self.sio = sio
        self.notification_service = notification_service
        self.register_handlers()

    def register_handlers(self):
        @self.sio.on("join_notification_room")
        async def on_join_notification_room(sid, data):
            try:
                user_id = data.get("user_id")
                if not user_id:
                    await self.sio.emit("error", {
                        "message": "user_id is required",
                        "event": "join_notification_room"
                    }, room=sid)
                    return

                room = f"notify:{user_id}"
                await self.sio.enter_room(sid, room)
                await self.sio.save_session(sid, {"user_id": user_id})

                await self.sio.emit("joined_notification_room", {
                    "room": room,
                    "status": "success"
                }, room=sid)

            except Exception as e:
                traceback.print_exc()
                await self.sio.emit("error", {
                    "message": f"Failed to join notification room: {str(e)}",
                    "event": "join_notification_room"
                }, room=sid)

        @self.sio.on("get_notifications")
        async def on_get_notifications(sid, data):
            try:
                session = await self.sio.get_session(sid)
                user_id = data.get("user_id") or session.get("user_id")

                if not user_id:
                    await self.sio.emit("error", {
                        "message": "user_id is required",
                        "event": "get_notifications"
                    }, room=sid)
                    return

                notifications = await self.notification_service.get_notifications(user_id)

                await self.sio.emit("notifications", {
                    "notifications": [n.to_json() for n in notifications],
                    "timestamp": time.time()
                }, room=sid)

            except Exception as e:
                traceback.print_exc()
                await self.sio.emit("error", {
                    "message": f"Failed to get notifications: {str(e)}",
                    "event": "get_notifications"
                }, room=sid)

        @self.sio.on("send_notification")
        async def on_send_notification(sid, data):
            try:
                required_fields = ["to_id", "message"]
                for field in required_fields:
                    if field not in data or not data[field]:
                        await self.sio.emit("error", {
                            "message": f"{field} is required",
                            "event": "send_notification"
                        }, room=sid)
                        return

                notif = await self.notification_service.create_notification(data)
                room = f"notify:{data['to_id']}"
                await self.sio.emit("new_notification", notif.to_json(), room=room)
            except Exception as e:
                traceback.print_exc()
                await self.sio.emit("error", {
                    "message": f"Failed to send notification: {str(e)}",
                    "event": "send_notification",
                    "original_data": data
                }, room=sid)
