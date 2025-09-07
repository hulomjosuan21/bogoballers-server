import traceback
from quart import Blueprint, request, jsonify

from src.services.message_service import MessageService
from src.utils.api_response import ApiResponse
from src.utils.server_utils import validate_required_fields

message_bp = Blueprint('message', __name__, url_prefix='/message')

service = MessageService()

@message_bp.post('/send')
async def send_message_route():
    try:
        enable_notification = request.args.get("enable_notification", "true").lower() == "true"
        data = await request.get_json()
        
        validate_required_fields(data, ["sender_id", "receiver_id", "content"])
        result = await service.send_message_notification(
            data=data, 
            enable_notification=enable_notification
        )
        
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@message_bp.get('/conversations/<user_id>')
async def get_conversations_route(user_id: str):
    try:
        conversations = await service.get_conversations(user_id)
        return await ApiResponse.payload(conversations)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@message_bp.get('/conversation/<user_id>/<partner_id>')
async def get_conversation_messages_route(user_id: str, partner_id: str):
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
        
        result = await service.get_conversation_messages(
            user_id=user_id,
            partner_id=partner_id,
            limit=limit,
            offset=offset
        )
        return await ApiResponse.payload(result)
        
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@message_bp.post('/mark-read')
async def mark_messages_read_route():
    try:
        data = await request.get_json()
        validate_required_fields(data, ["user_id", "partner_id"])
        result = await service.mark_messages_as_read(
            user_id=data["user_id"],
            conversation_partner_id=data["partner_id"]
        )
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@message_bp.get('/unread-count/<user_id>')
async def get_unread_count_route(user_id: str):
    try:
        result = await service.get_unread_message_count(user_id)
        return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@message_bp.delete('/delete/<message_id>')
async def delete_message_route(message_id: str):
    try:
        data = await request.get_json()
        validate_required_fields(data, ["user_id"])
        result = await service.delete_message(
            message_id=message_id,
            user_id=data["user_id"]
        )
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@message_bp.get('/health')
async def health_check():
    return await ApiResponse.success(message="Message service is healthy")

@message_bp.get('/socket/status')
async def socket_status():
    try:
        from src.extensions import sio
        status = {
            "connected": True,
            "namespace": "/",
            "rooms_count": len(sio.manager.rooms.get("/", {})),
            "timestamp": sio.manager.clock.time()
        }
        return await ApiResponse.payload(status)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)