import traceback
from quart import Blueprint, request

from src.utils.api_response import ApiResponse

league_player = Blueprint('league-player',__name__,url_prefix='/league-player')