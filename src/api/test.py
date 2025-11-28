from quart import Blueprint
from src.extensions import AsyncSession
from src.utils.api_response import ApiResponse
from src.utils.notification_utils import get_valid_fcm_for_match

test_bp = Blueprint('test', __name__, url_prefix='/test')

@test_bp.get('/fcms/<league_match_id>/<limit>')
async def get_fcms(league_match_id: str, limit: str):
    async with AsyncSession() as session:
        result = await get_valid_fcm_for_match(
            session,
            league_match_id=league_match_id,
            limit=int(limit)
        )
        
        return await ApiResponse.payload(result)