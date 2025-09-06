import traceback
from quart import Blueprint, request

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
        validate_required_fields(data, ["sender_id","receiver_id","content"])
        
        result = await service.send_message_notification(data=data, enable_notification=enable_notification)
        
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@message_bp.get('/conversation/<user_id>')
async def get_conversations(user_id: str):
    try:
        result = await service.get_conversations(user_id)
        
        return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)