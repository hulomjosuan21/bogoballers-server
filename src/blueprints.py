from src.handlers.static_data_handler import static_data_bp
from src.services.email_verification import auth_bp
from src.api.league_admin_routes import league_admin_bp
from src.api.entity_routes import entity_bp
from src.api.player.player_routes import player_bp
from src.api.team_manager_routes import team_mananger_bp
from src.api.team.team_routes import team_bp
from src.api.team.player_team_routes import player_team_bp
from src.api.category_routes import category_bp
from src.api.league.league_round_routes import round_bp
from src.api.league.league_routes import league_bp
from src.api.league.league_category_routes import league_category_bp
from src.api.league.league_team_routes import league_team_bp

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
    round_bp,
    category_bp,
    league_team_bp
]