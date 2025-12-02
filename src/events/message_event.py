import time
import socketio
import traceback
from src.services.message_service import MessageService

class MessageEvent:
    def __init__(self, sio: socketio.AsyncServer, message_service: MessageService):
        self.sio = sio
        self.message_service = message_service
        self.register_handlers()

    def register_handlers(self):
        @self.sio.on('connect')
        async def on_connect(sid, environ, auth):
            try:
                print(f"Client {sid} connected")
            except Exception as e:
                print(f"Connect error: {e}")

        @self.sio.on('disconnect')
        async def on_disconnect(sid):
            try:
                print(f"Client {sid} disconnected")
            except Exception as e:
                print(f"Disconnect error: {e}")

        @self.sio.on('join_user_room')
        async def on_join_user_room(sid, data):
            try:
                user_id = data.get('user_id')
                if user_id:
                    room = f"user:{user_id}"
                    await self.sio.enter_room(sid, room)
                    await self.sio.save_session(sid, {'user_id': user_id})
                    await self.sio.emit('joined_room', {
                        'room': room,
                        'status': 'success'
                    }, room=sid)
                else:
                    await self.sio.emit('error', {
                        'message': 'user_id is required',
                        'event': 'join_user_room'
                    }, room=sid)
            except Exception as e:
                traceback.print_exc()
                await self.sio.emit('error', {
                    'message': f'Failed to join room: {str(e)}',
                    'event': 'join_user_room'
                }, room=sid)

        @self.sio.on('get_conversations')
        async def on_get_conversations(sid, data):
            try:
                user_id = data.get('user_id')
                if not user_id:
                    session = await self.sio.get_session(sid)
                    user_id = session.get('user_id')
                    
                if not user_id:
                    await self.sio.emit('error', {
                        'message': 'user_id is required',
                        'event': 'get_conversations'
                    }, room=sid)
                    return
                room = f"user:{user_id}"
                await self.sio.enter_room(sid, room)
                
                conversations = await self.message_service.get_conversations(user_id)
                
                await self.sio.emit('conversations', {
                    'conversations': conversations,
                    'user_id': user_id,
                    'timestamp': time.time()
                }, room=sid)
                
            except Exception as e:
                traceback.print_exc()
                await self.sio.emit('error', {
                    'message': f'Failed to get conversations: {str(e)}',
                    'event': 'get_conversations'
                }, room=sid)

        @self.sio.on('send_message')
        async def on_send_message(sid, data):
            try:
                required_fields = ['sender_id', 'receiver_id', 'content']
                for field in required_fields:
                    if field not in data or not data[field]:
                        await self.sio.emit('error', {
                            'message': f'{field} is required',
                            'event': 'send_message'
                        }, room=sid)
                        return

                sender_room = f"user:{data['sender_id']}"
                await self.sio.enter_room(sid, sender_room)
                    
                result = await self.message_service.send_message_notification(
                    data=data,
                    enable_notification=True
                )
                
            except Exception as e:
                traceback.print_exc()
                await self.sio.emit('error', {
                    'status': 'error',
                    'message': f'Failed to send message: {str(e)}',
                    'original_data': data
                }, room=sid)