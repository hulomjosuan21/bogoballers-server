import traceback
from quart import Blueprint, request, jsonify
from sqlalchemy import select
from src.models.league_log_model import LeagueLogModel
from src.services.ai_auto_match_service import AutoMatchService
from src.extensions import AsyncSession
from src.utils.api_response import ApiResponse

auto_matcher_bp = Blueprint('ai-matcher', __name__, url_prefix='/ai-auto-match')

@auto_matcher_bp.route('/generate', methods=['POST'])
async def generate_matches():
    """
    Called when user clicks 'Generate Matches' (Play button)
    """
    try:
        data = await request.get_json()
        round_id = data.get('round_id')

        if not round_id:
            return jsonify({"error": "round_id required"}), 400

        async with AsyncSession() as session:
            service = AutoMatchService(session)
            
            # 1. Get Context
            context, round_obj = await service.get_round_context(round_id)
            
            # 2. Safety Check: Don't generate if matches exist (unless forced)
            if len(context['match_history']) > 0:
                return jsonify({"status": "error", "message": "Matches already exist. Use Reset or Progress."}), 400

            # 3. AI Decision
            decision = await service.consult_ai(context, mode="generate")
            
            # 4. Execute
            await service.execute_decision(decision, round_obj, action_type="generate")
            
            # Mark as generated
            round_obj.matches_generated = True
            await session.commit()

        return await ApiResponse.payload({
            "status": "success", 
            "explanation": decision.explanation,
            "matches_created": len(decision.create_matches)
        })
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)


@auto_matcher_bp.route('/progress', methods=['POST'])
async def progress_round():
    """
    Called when user clicks 'Progress Round' (Fast Forward button)
    Checks results, eliminates teams, creates next stage matches.
    """
    try:
        data = await request.get_json()
        round_id = data.get('round_id')

        async with AsyncSession() as session:
            service = AutoMatchService(session)
            context, round_obj = await service.get_round_context(round_id)
            
            # AI Decision
            decision = await service.consult_ai(context, mode="progress")
            
            # Execute
            await service.execute_decision(decision, round_obj, action_type="progress")

        return await ApiResponse.payload({
            "status": "success", 
            "explanation": decision.explanation,
            "updates": {
                "teams_updated": len(decision.update_teams),
                "matches_created": len(decision.create_matches)
            }
        })
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@auto_matcher_bp.route('/reset', methods=['POST'])
async def reset_round():
    """
    Hard Reset: Deletes all matches in the round, un-eliminates teams.
    """
    try:
        data = await request.get_json()
        round_id = data.get('round_id')

        async with AsyncSession() as session:
            from src.models.match import LeagueMatchModel
            
            stmt = select(LeagueMatchModel).where(LeagueMatchModel.round_id == round_id)
            res = await session.execute(stmt)
            matches = res.scalars().all()
            
            for m in matches:
                await session.delete(m)
                
            service = AutoMatchService(session)
            _, round_obj = await service.get_round_context(round_id)
            round_obj.matches_generated = False
            round_obj.round_status = "Upcoming"
            round_obj.current_stage = 0
            
            for team in round_obj.league_category.teams:
                team.is_eliminated = False
                team.status = "Pending" # or Active
                team.final_rank = None
                team.is_champion = False

            await session.commit()
            
        return await ApiResponse.payload({"status": "success", "message": "Round reset completely."})
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)