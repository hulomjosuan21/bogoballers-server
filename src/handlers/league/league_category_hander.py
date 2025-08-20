from quart import Blueprint, request
from quart_auth import login_required
from sqlalchemy import select
from src.extensions import AsyncSession
from src.models.league import LeagueCategoryModel, LeagueCategoryRoundModel
from src.utils.api_response import ApiException, ApiResponse

league_category_bp = Blueprint("league-category", __name__, url_prefix="/league/category")

class LeagueCategoryHandler:
    @staticmethod
    @league_category_bp.post("/category_id>/save-changes")
    @login_required
    async def save_changes(category_id: str):
        try:
            data = await request.get_json()
            if not data or "operations" not in data:
                raise ApiException("Missing 'operations' in request body")
            operations = data["operations"]
            
            ROUND_ORDER_MAP = {
                "Elimination": 0,
                "Quarterfinal": 1,
                "Semifinal": 2,
                "Final": 3,
            }
            async with AsyncSession() as session:
                results = []
                
                for operation in operations:
                    op_type = operation.get("type")
                    op_data = operation.get("data", {})
                    
                    if op_type == "create_round":
                        round_name = op_data.get("round_name")
                        round_id = op_data.get("round_id")
                        
                        if not round_name or not round_id:
                            continue
                        
                        round_order = ROUND_ORDER_MAP.get(round_name, op_data.get("round_order", 0))
                        
                        new_round = LeagueCategoryRoundModel(
                            round_id=round_id,
                            category_id=category_id,
                            round_name=round_name,
                            round_order=round_order,
                            round_status=op_data.get("round_status", "Upcoming"),
                            position=op_data.get("position")
                        )
                        session.add(new_round)
                        results.append({
                            "operation": "create_round",
                            "round_id": round_id,
                            "status": "success"
                        })
                    
                    elif op_type == "update_position":
                        round_id = op_data.get("round_id")
                        position = op_data.get("position")
                        
                        if not round_id or not position:
                            continue
                        
                        result = await session.execute(
                            select(LeagueCategoryRoundModel)
                            .where(LeagueCategoryRoundModel.category_id == category_id)
                            .where(LeagueCategoryRoundModel.round_id == round_id)
                        )
                        round_obj = result.scalar_one_or_none()
                        
                        if round_obj:
                            round_obj.position = position
                            results.append({
                                "operation": "update_position",
                                "round_id": round_id,
                                "status": "success"
                            })
                    
                    elif op_type == "update_format":
                        round_id = op_data.get("round_id")
                        round_format = op_data.get("round_format")
                        
                        if not round_id:
                            continue
                        
                        result = await session.execute(
                            select(LeagueCategoryRoundModel)
                            .where(LeagueCategoryRoundModel.category_id == category_id)
                            .where(LeagueCategoryRoundModel.round_id == round_id)
                        )
                        round_obj = result.scalar_one_or_none()
                        
                        if round_obj:
                            round_obj.round_format = round_format
                            results.append({
                                "operation": "update_format",
                                "round_id": round_id,
                                "status": "success"
                            })

                await session.commit()
                
                return await ApiResponse.success(
                    message=f"Successfully processed {len(results)} operations",
                    payload={"results": results}
                )

        except Exception as e:
            return await ApiResponse.error(e)    
    
    @league_category_bp.post("/<category_id>/round/<round_id>/update-format")
    @login_required
    async def update_round_format(category_id: str, round_id: str):
        try:
            data = await request.get_json()
            if not data or "round_format" not in data:
                raise ApiException("Missing format in request body")

            async with AsyncSession() as session:
                result = await session.execute(
                    select(LeagueCategoryRoundModel)
                    .where(LeagueCategoryRoundModel.category_id == category_id)
                    .where(LeagueCategoryRoundModel.round_id == round_id)
                )
                round_obj = result.scalar_one_or_none()

                if not round_obj:
                    raise ApiException("Round not found")

                round_obj.round_format = data["round_format"]

                await session.commit()
                await session.refresh(round_obj)

                return await ApiResponse.success(
                    message="Round format updated successfully",
                    payload={"round_id": round_obj.round_id, "round_format": round_obj.round_format}
                )

        except Exception as e:
            return await ApiResponse.error(e)
        
    @staticmethod
    @league_category_bp.post("/<string:league_id>/add-category")
    @login_required
    async def add_category(league_id: str):
        try:
            data = await request.get_json()
            if not data:
                raise ApiException("Missing request body")

            required_fields = ["category_name"]
            for field in required_fields:
                if not data.get(field):
                    raise ApiException(f"{field} is required")

            max_team = int(data.get("max_team", 4))
            team_entrance_fee_amount = float(data.get("team_entrance_fee_amount", 0.0))
            individual_player_entrance_fee_amount = float(data.get("individual_player_entrance_fee_amount", 0.0))

            async with AsyncSession() as session:
                new_category = LeagueCategoryModel(
                    league_id=league_id,
                    category_name=data["category_name"],
                    max_team=max_team,
                    team_entrance_fee_amount=team_entrance_fee_amount,
                    individual_player_entrance_fee_amount=individual_player_entrance_fee_amount
                )

                session.add(new_category)
                await session.commit()

            return await ApiResponse.success(message="Category added successfully")

        except Exception as e:
            return await ApiResponse.error(e)