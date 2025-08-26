from src.handlers.static_data_handler import static_data_bp
from src.handlers.league_admin_handler import league_admin_bp
from src.services.email_verification import auth_bp
from src.handlers.league.league_handler import league_bp
from src.handlers.league.league_category_hander import league_category_bp
from src.handlers.entity_handler import entity_bp
from src.handlers.player.player_handler import player_bp
from src.handlers.team_manager_handler import team_mananger_bp
from src.handlers.team.player_team_handler import player_team_bp
from src.handlers.team.team_handler import team_bp
from src.handlers.category_handler import category_bp
from src.handlers.league.league_round_handler import round_bp

all_blueprints = [
    static_data_bp,
    league_admin_bp,
    auth_bp,
    league_bp,
    league_category_bp,
    entity_bp,
    player_bp,
    team_mananger_bp,
    player_team_bp,
    team_bp,
    category_bp,
    round_bp
]