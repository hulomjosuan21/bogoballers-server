from src.handlers.static_data_handler import static_data_bp
from src.handlers.league_admin_handler import league_admin_bp
from src.services.email_verification import auth_bp
from src.handlers.league_handler import league_bp
from src.handlers.entity_handler import entity_bp
from src.handlers.player_handler import player_bp
from src.handlers.team_manager_handler import team_mananger_bp
all_blueprints = [
    static_data_bp,
    league_admin_bp,
    auth_bp,
    league_bp,
    entity_bp,
    player_bp,
    team_mananger_bp
]