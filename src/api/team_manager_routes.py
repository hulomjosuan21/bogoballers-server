import traceback
from quart import Blueprint, request
from quart_auth import login_required, current_user
from src.utils.api_response import ApiResponse
from src.services.team_manager_service import TeamManagerService
from src.utils.server_utils import validate_required_fields

team_mananger_bp = Blueprint("team_manager", __name__, url_prefix="/team-manager")