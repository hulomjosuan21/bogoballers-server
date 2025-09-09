import traceback
from quart import Blueprint, request

from src.services.notification_service import NotificationService
from src.utils.api_response import ApiResponse

notification_bp = Blueprint('notification',__name__,url_prefix='/notif')

service = NotificationService()

@notification_bp.post('/send')
async def send_notif_route():
    try:
        data = await request.get_json()
        result = await service.create_notification(data)
        
        return await ApiResponse.payload(result.to_json())
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)