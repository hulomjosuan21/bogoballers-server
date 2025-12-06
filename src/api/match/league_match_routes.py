import traceback
from quart import Blueprint, request
from src.models.team import LeagueTeamModel
from src.models.match import LeagueMatchModel
from src.extensions import AsyncSession
from src.services.match.match_service import LeagueMatchService
from src.utils.api_response import ApiException, ApiResponse
from src.utils.db_utils import str_to_bool
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
league_match_bp = Blueprint('league-match', __name__, url_prefix='/league-match')
    
service = LeagueMatchService()

@league_match_bp.post('/matches/all/<user_id>')
async def get_all_matches(user_id: str):
    try:
        data = await request.get_json()
        result = await service.get_user_matches(user_id, data)
        
        return await ApiResponse.payload([r.to_json() for r in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
        
@league_match_bp.put('/<league_match_id>/finalize')
async def finalize_one_match_route(league_match_id: str):
    try:
        data = await request.get_json()
        result = await service.finalize_match_result(league_match_id,data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_match_bp.put('/<league_round_id>')
async def get_update_one_route(league_round_id: str):
    try:
        data = await request.get_json()
        result = await service.update_one(league_round_id,data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_match_bp.post('/all/<league_category_id>/<round_id>')
async def get_many_route(league_category_id: str, round_id: str):
    try:
        data = await request.get_json()
        result = await service.get_many(league_category_id,round_id,data)
        return await ApiResponse.payload([r.to_json() for r in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_match_bp.post('/generate/elimination/<league_id>/<elimination_round_id>')
async def generate_elimination_round_route(league_id: str,elimination_round_id: str):
    try:
        result = await service.generate_first_elimination_round(league_id, elimination_round_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_match_bp.put('/progress-next/<league_id>/<current_round_id>')
async def progress_next_round_route(league_id: str, current_round_id: str):
    try:
        auto_proceed_str = request.args.get("auto_proceed", "false")
        
        auto_proceed  = str_to_bool(auto_proceed_str)
        
        result = await service.progress_to_next_round(league_id, current_round_id, auto_proceed)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_match_bp.post('/generate/finalize/<final_round_id>')
async def finalize_tournament_results_route(final_round_id: str):
    try:
        result = await service.finalize_tournament_results(final_round_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_match_bp.get('/<league_match_id>')
async def get_one_route(league_match_id: str):
    try:
        result = await service.get_one(league_match_id)
        return await ApiResponse.payload(result.to_json())
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_match_bp.get('/<league_category_id>/<round_id>/unscheduled')
async def fetch_unscheduled_route(league_category_id: str, round_id: str):
    try:
        result = await service.fetch_unscheduled(
            league_category_id=league_category_id,
            round_id=round_id
        )
        return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_match_bp.get('/<league_category_id>/<round_id>/scheduled')
async def fetch_scheduled_route(league_category_id: str, round_id: str):
    try:
        result = await service.fetch_scheduled(league_category_id=league_category_id,round_id=round_id)
        return await ApiResponse.payload([r.to_json() for r in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_match_bp.get('/<league_category_id>/<round_id>/completed')
async def fetch_completed_route(league_category_id: str, round_id: str):
    try:
        result = await service.fetch_completed(league_category_id=league_category_id,round_id=round_id)
        return await ApiResponse.payload([r.to_json() for r in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_match_bp.patch('/<match_id>/score')
async def update_match_score(match_id: str):
    async with AsyncSession() as session:
        try:
            data = await request.get_json()
            home_score = data.get('home_score')
            away_score = data.get('away_score')

            if home_score is None or away_score is None:
                raise ApiException("Both 'home_score' and 'away_score' are required")
            if not isinstance(home_score, int) or home_score < 0:
                raise ApiException("Home score must be a non-negative integer")
            if not isinstance(away_score, int) or away_score < 0:
                raise ApiException("Away score must be a non-negative integer")
            
            if home_score == away_score:
                raise ApiException("Draws are not allowed. Please enter the final score after Overtime.")

            match = await session.get(LeagueMatchModel, match_id)
            if not match:
                raise ApiException("Match not found")

            home_team = await session.get(LeagueTeamModel, match.home_team_id)
            away_team = await session.get(LeagueTeamModel, match.away_team_id)

            if not home_team or not away_team:
                raise ApiException("One or both teams not found in league records")

            match.home_team_score = home_score
            match.away_team_score = away_score
            match.status = "Completed"

            home_team.points += home_score
            away_team.points += away_score
            if match.home_team_score > match.away_team_score:
                match.winner_team_id = match.home_team_id
                match.loser_team_id = match.away_team_id
                
                home_team.wins += 1
                away_team.losses += 1

            elif match.away_team_score > match.home_team_score:
                match.winner_team_id = match.away_team_id
                match.loser_team_id = match.home_team_id
                
                away_team.wins += 1
                home_team.losses += 1

            await session.commit()

            return await ApiResponse.success(message="Scores updated and team stats incremented")

        except (IntegrityError, SQLAlchemyError) as se:
            traceback.print_exc()
            await session.rollback()
            return await ApiResponse.error(se)
        except Exception as e:
            traceback.print_exc()
            return await ApiResponse.error(e)