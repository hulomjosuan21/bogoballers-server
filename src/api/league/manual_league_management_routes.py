import traceback
from quart import Blueprint, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.models.team import LeagueTeamModel
from src.models.match import LeagueMatchModel
from src.extensions import AsyncSession
from src.services.league.league_manual_management import ManualLeagueManagementService
from src.utils.api_response import ApiException, ApiResponse

manual_league_management_bp = Blueprint('manual-league-management', __name__, url_prefix='/manual-league-management')

service = ManualLeagueManagementService()

@manual_league_management_bp.get("/match-count/<round_id>")
async def get_match_count(round_id: str):
    try:
        service = ManualLeagueManagementService()
        group_id = request.args.get('group_id', None)
        count = await service.count_matches_in_round(round_id, group_id)
        return await ApiResponse.payload({"count": count})
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@manual_league_management_bp.get('/flow-state/<string:league_id>')
async def get_flow_state_route(league_id: str):
    try:
        flow_state = await service.get_flow_state(league_id)
        return await ApiResponse.payload(flow_state)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@manual_league_management_bp.post('/rounds')
async def create_round_route():
    try:
        data = await request.get_json()
        new_round = await service.create_new_round(
            league_category_id=data.get("league_category_id"),
            round_name=data.get("round_name"),
            round_order=data.get("round_order"),
            position=data.get("position")
        )
        return await ApiResponse.payload(new_round)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@manual_league_management_bp.post('/matches')
async def create_match_route():
    try:
        data = await request.get_json()
        new_match = await service.create_empty_match(
            league_id=data.get("league_id"),
            league_category_id=data.get("league_category_id"),
            round_id=data.get("round_id"),
            display_name=data.get("display_name"),
            position=data.get("position"),
            group_id=data.get('group_id', None),
            is_elimination=data.get("is_elimination", False),
            is_round_robin=data.get("is_round_robin", False),
            is_third_place=data.get("is_third_place", False),
            is_final=data.get("is_final", False),
        )
        return await ApiResponse.payload(new_match)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@manual_league_management_bp.post('/groups')
async def create_group_route():
    try:
        data = await request.get_json()
        new_group = await service.create_group(
            league_category_id=data.get("league_category_id"),
            round_id=data.get("round_id"),
            round_name=data.get("round_name"),
            display_name=data.get("display_name"),
            position=data.get("position")
        )
        return await ApiResponse.payload(new_group)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@manual_league_management_bp.post('/edges')
async def create_edge_route():
    try:
        data = await request.get_json()
        new_edge = await service.create_edge(
            league_id=data.get("league_id"),
            league_category_id=data.get("league_category_id"),
            source_id=data.get("source"),
            target_id=data.get("target"),
            source_handle=data.get("sourceHandle"),
            target_handle=data.get("targetHandle")
        )
        return await ApiResponse.payload(new_edge)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@manual_league_management_bp.put('/groups/<string:group_id>')
async def update_group_route(group_id: str):
    try:
        data = await request.get_json()
        updated_group = await service.update_group(group_id, data)
        return await ApiResponse.payload(updated_group)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@manual_league_management_bp.put('/matches/<string:match_id>/assign-team')
async def assign_team_route(match_id: str):
    try:
        data = await request.get_json()
        updated_match = await service.assign_team_to_match(
            match_id=match_id,
            team_id=data.get("team_id"),
            slot=data.get("slot")
        )
        return await ApiResponse.payload(updated_match)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@manual_league_management_bp.put('/matches/<string:match_id>')
async def update_match_route(match_id: str):
    try:
        data = await request.get_json()
        updated_match = await service.update_match_connections(match_id, data)
        return await ApiResponse.payload(updated_match)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@manual_league_management_bp.put('/nodes/<string:node_type>/<string:node_id>/position')
async def update_node_position_route(node_type: str, node_id: str):
    try:
        data = await request.get_json()
        success = await service.update_node_position(
            node_id=node_id,
            node_type=node_type,
            position=data.get("position")
        )
        if success:
            return await ApiResponse.success(message="Position updated.")
        return await ApiResponse.error("Node not found.", status_code=404)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@manual_league_management_bp.delete('/edges/<string:edge_id>')
async def delete_edge_route(edge_id: str):
    try:
        success = await service.delete_edge(edge_id)
        if success:
            return await ApiResponse.success(message="Edge deleted.")
        return await ApiResponse.error("Edge not found.", status_code=404)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

@manual_league_management_bp.delete('/nodes/<string:node_type>/<string:node_id>')
async def delete_single_node_route(node_type: str, node_id: str):
    try:
        success = await service.delete_single_node(node_id, node_type)
        if success:
            return await ApiResponse.success(message="Node deleted.")
        return await ApiResponse.error("Node not found.", status_code=404)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))
    
@manual_league_management_bp.post('/leagues/<string:league_category_id>/synchronize')
async def synchronize_bracket_route(league_category_id: str):
    try:
        result = await service.synchronize_bracket(league_category_id)
        return await ApiResponse.success(message=f"Bracket synchronized. {result.get('teams_progressed', 0)} teams progressed.")
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))  
    
@manual_league_management_bp.put('/<match_id>/score')
async def update_match_score(
    match_id: str,
):
    async with AsyncSession() as session:
        try:
            data = await request.get_json()
            slot = data.get('slot')
            score = data.get('score')

            if slot not in ['home', 'away']:
                raise ApiException("Slot must be 'home' or 'away'")

            if not isinstance(score, int) or score < 0:
                raise ApiException("Score must be a non-negative integer")

            result = await session.execute(
                select(LeagueMatchModel).where(LeagueMatchModel.league_match_id == match_id)
            )
            match = result.scalar_one_or_none()

            if not match:
                raise ApiException("Match not found")

            if slot == "home":
                match.home_team_score = score
            else:
                match.away_team_score = score

            if match.home_team_score is not None and match.away_team_score is not None:
                if match.home_team_score > match.away_team_score:
                    match.winner_team_id = match.home_team_id
                    match.loser_team_id = match.away_team_id
                elif match.away_team_score > match.home_team_score:
                    match.winner_team_id = match.away_team_id
                    match.loser_team_id = match.home_team_id
                else:
                    match.winner_team_id = None
                    match.loser_team_id = None

            await session.commit()

            return await ApiResponse.success(message="Score updated successfully")
        except (IntegrityError, SQLAlchemyError) as se:
            traceback.print_exc()
            await session.rollback()
            return await ApiResponse.error(se)
        except Exception as e:
            traceback.print_exc()
            return await ApiResponse.error(e)
        
@manual_league_management_bp.put("/<team_id>/eliminate")
async def eliminate_team(team_id: str):
    async with AsyncSession() as session:
        try:
            result = await session.execute(
                select(LeagueTeamModel).where(LeagueTeamModel.league_team_id == team_id)
            )
            team = result.scalar_one_or_none()

            if not team:
                raise ApiException("Team not found")

            if team.is_eliminated:
                raise ApiException("Team already eliminated")

            active_count_result = await session.execute(
                select(func.count()).select_from(LeagueTeamModel)
                .where(
                    LeagueTeamModel.league_category_id == team.league_category_id,
                    LeagueTeamModel.is_eliminated.is_(False)
                )
            )
            active_count = active_count_result.scalar_one()

            team.is_eliminated = True
            team.final_rank = active_count
            # team.finalized_at = datetime.utcnow()

            await session.commit()

            return await ApiResponse.success(
                message=f"Team eliminated — ranked #{active_count}",
            )
        except (IntegrityError, SQLAlchemyError) as se:
            traceback.print_exc()
            await session.rollback()
            return await ApiResponse.error(se)
        except Exception as e:
            traceback.print_exc()
            return await ApiResponse.error(e)