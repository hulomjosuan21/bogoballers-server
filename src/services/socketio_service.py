import traceback
import socketio
import redis.asyncio as aioredis
from src.utils.rate_limiter import socket_rate_limit, increment_limit

import socketio
from socketio.async_redis_manager import AsyncRedisManager
from src.config import Config

class SocketIOService:
    def __init__(self, redis_url: str = None):
        self.sio = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins='*',
            client_manager=AsyncRedisManager(redis_url) if redis_url else None
        )

        self.app = socketio.ASGIApp(self.sio, static_files={})
        
        self.message_service = None

        self.register_handlers()

    def _get_message_service(self):
        if self.message_service is None:
            from src.services.message_service import MessageService
            self.message_service = MessageService()
        return self.message_service

    def register_handlers(self):
        sio = self.sio

        @sio.event
        async def connect(sid, environ, auth):
            query_params = {}
            if 'QUERY_STRING' in environ:
                from urllib.parse import parse_qs
                query_params = parse_qs(environ['QUERY_STRING'])
            
            user_id = None
            if 'user_id' in query_params:
                user_id = query_params['user_id'][0]
            elif auth and 'user_id' in auth:
                user_id = auth['user_id']
                

            
            if user_id:
                await sio.save_session(sid, {'user_id': user_id})

        @sio.event
        async def disconnect(sid):
            print(f"Socket disconnected: {sid}")

        @sio.on('join')
        async def on_join(sid, data):
            user_id = data.get("user_id")
            entity_id = data.get("entity_id")
            
            if user_id:
                room = f"user:{user_id}"
                await sio.enter_room(sid, room)

                

                session = await sio.get_session(sid)
                session['user_id'] = user_id
                await sio.save_session(sid, session)
                
            if entity_id:
                room = f"entity:{entity_id}"
                await sio.enter_room(sid, room)


        @sio.on('leave')
        async def on_leave(sid, data):
            user_id = data.get("user_id")
            entity_id = data.get("entity_id")
            
            if user_id:
                room = f"user:{user_id}"
                await sio.leave_room(sid, room)

                
            if entity_id:
                room = f"entity:{entity_id}"
                await sio.leave_room(sid, room)


        @sio.on('get_conversations')
        async def on_get_conversations(sid, data):
            try:
                user_id = data.get('user_id')
                if not user_id:

                    session = await sio.get_session(sid)
                    user_id = session.get('user_id')
                    
                if not user_id:
                    await sio.emit('error', {
                        'message': 'user_id is required',
                        'event': 'get_conversations'
                    }, room=sid)
                    return

                message_service = self._get_message_service()
                conversations = await message_service.get_conversations(user_id)
                
                await sio.emit('conversations', {
                    'conversations': conversations,
                    'user_id': user_id,
                    'timestamp': sio.manager.clock.time()
                }, room=sid)
                
            except Exception as e:

                traceback.print_exc()
                await sio.emit('error', {
                    'message': f'Failed to get conversations: {str(e)}',
                    'event': 'get_conversations'
                }, room=sid)

        @sio.on('send_message')
        async def on_send_message(sid, data):
            try:

                required_fields = ['sender_id', 'receiver_id', 'content']
                for field in required_fields:
                    if field not in data or not data[field]:
                        await sio.emit('error', {
                            'message': f'{field} is required',
                            'event': 'send_message'
                        }, room=sid)
                        return
                    
                message_service = self._get_message_service()
                result = await message_service.send_message_notification(
                    data=data,
                    enable_notification=True
                )
                
                await sio.emit('message_sent', {
                    'status': 'success',
                    'message': result,
                    'original_data': data
                }, room=sid)
                
            except Exception as e:

                traceback.print_exc()
                await sio.emit('message_sent', {
                    'status': 'error',
                    'message': f'Failed to send message: {str(e)}',
                    'original_data': data
                }, room=sid)

        @sio.on('register')
        async def on_register(sid, data):
            user_id = data.get("user_id")
            if user_id:
                room = f"user:{user_id}"
                await sio.enter_room(sid, room)
                

                session = await sio.get_session(sid)
                session['user_id'] = user_id
                await sio.save_session(sid, session)
                
        @sio.on('ping')
        async def on_ping(sid, data):
            await sio.emit('pong', {
                'timestamp': sio.manager.clock.time(),
                'data': data
            }, room=sid)