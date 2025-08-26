from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from quart import Blueprint, request
from quart_auth import login_required
from sqlalchemy import select, update
from src.extensions import AsyncSession
from src.models.league import LeagueCategoryModel, LeagueCategoryRoundModel
from src.utils.api_response import ApiException, ApiResponse
from sqlalchemy.orm import joinedload
league_category_bp = Blueprint("league-category", __name__, url_prefix="/league/category")

class LeagueCategoryHandler:
    @staticmethod
    @league_category_bp.post("/<league_category_id>/save-changes")
    @login_required
    async def save_changes(league_category_id: str):
        try:
            data = await request.get_json()
            if not data or "operations" not in data:
                raise ApiException("Missing 'operations' in request body")
            operations = data["operations"]
            
            for i, op in enumerate(operations):
                print(f"Operation {i+1}: {op.get('type')} - {op.get('data', {})}")
            
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
                            league_category_id=league_category_id,
                            round_name=round_name,
                            round_order=round_order,
                            round_status=op_data.get("round_status", "Upcoming"),
                            position=op_data.get("position"),
                            next_round_id=op_data.get("next_round_id")
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
                            .where(LeagueCategoryRoundModel.league_category_id == league_category_id)
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
                            .where(LeagueCategoryRoundModel.league_category_id == league_category_id)
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
                    
                    elif op_type == "update_next_round":
                        round_id = op_data.get("round_id")
                        next_round_id = op_data.get("next_round_id")
                        
                        if not round_id:
                            continue
                        
                        result = await session.execute(
                            select(LeagueCategoryRoundModel)
                            .where(LeagueCategoryRoundModel.league_category_id == league_category_id)
                            .where(LeagueCategoryRoundModel.round_id == round_id)
                        )
                        round_obj = result.scalar_one_or_none()
                        
                        if round_obj:
                            round_obj.next_round_id = next_round_id
                            results.append({
                                "operation": "update_next_round",
                                "round_id": round_id,
                                "status": "success"
                            })
                        else:
                            results.append({
                                "operation": "update_next_round",
                                "round_id": round_id,
                                "status": "error",
                                "message": "Round not found"
                            })
                    
                    elif op_type == "delete_round":
                        round_id = op_data.get("round_id")
                        
                        if not round_id:
                            continue
                        
                        result = await session.execute(
                            select(LeagueCategoryRoundModel)
                            .where(LeagueCategoryRoundModel.league_category_id == league_category_id)
                            .where(LeagueCategoryRoundModel.round_id == round_id)
                        )
                        round_obj = result.scalar_one_or_none()
                        
                        if round_obj:
                            await session.execute(
                                update(LeagueCategoryRoundModel)
                                .where(LeagueCategoryRoundModel.league_category_id == league_category_id)
                                .where(LeagueCategoryRoundModel.next_round_id == round_id)
                                .values(next_round_id=None)
                            )
                            
                            await session.delete(round_obj)
                            results.append({
                                "operation": "delete_round",
                                "round_id": round_id,
                                "status": "success"
                            })
                        else:
                            results.append({
                                "operation": "delete_round",
                                "round_id": round_id,
                                "status": "error",
                                "message": "Round not found"
                            })

                await session.commit()
                
                return await ApiResponse.success(
                    message=f"Successfully processed {len(results)} operations",
                )

        except Exception as e:
            return await ApiResponse.error(e)
    
    @staticmethod
    @league_category_bp.post("/<league_category_id>/round/<round_id>/update-format")
    @login_required
    async def update_round_format(league_category_id: str, round_id: str):
        try:
            data = await request.get_json()
            if not data or "round_format" not in data:
                raise ApiException("Missing format in request body")

            async with AsyncSession() as session:
                result = await session.execute(
                    select(LeagueCategoryRoundModel)
                    .where(LeagueCategoryRoundModel.league_category_id == league_category_id)
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
    @league_category_bp.post("/<league_id>/add-category")
    @login_required
    async def add_league_category(league_id: str):
        try:
            category_ids = await request.get_json()

            if not category_ids or not isinstance(category_ids, list):
                raise ApiException("Request body must be a non-empty list of category IDs")
            if any(not cid for cid in category_ids):
                raise ApiException("All category IDs must be valid non-empty strings")

            async with AsyncSession() as session:
                for category_id in category_ids:
                    new_category = LeagueCategoryModel(
                        league_id=league_id,
                        category_id=category_id,
                    )
                    session.add(new_category)

                await session.commit()

            return await ApiResponse.success(message="Categories added successfully")

        except Exception as e:
            return await ApiResponse.error(e)
        
    @staticmethod
    @league_category_bp.get("/<league_id>")
    async def get_league_categories(league_id: str):
        try:
            
            if not league_id:
                raise ApiException("No league id.")
            
            async with AsyncSession() as session:
                result = await session.execute(
                    select(LeagueCategoryModel)
                    .options(
                        joinedload(LeagueCategoryModel.rounds),
                    )
                    .where(LeagueCategoryModel.league_id == league_id)
                )

                categories = result.unique().scalars().all()

                return await ApiResponse.payload([c.to_json() for c in categories])

        except Exception as e:
            return await ApiResponse.error(e)
    
    @staticmethod
    @league_category_bp.delete("/<league_category_id>")
    async def delete_League_category(league_category_id: str):
        try:
            async with AsyncSession() as session:
                category = await session.get(LeagueCategoryModel, league_category_id)

                if not category:
                    raise ApiException("Category not found.", 404)

                await session.delete(category)

                await session.commit()
                
            return await ApiResponse.success(
                message="Category deleted successfully",
            )

        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            return await ApiResponse.error(f"Error: {str(e)}")
        except Exception as e:
            return await ApiResponse.error(e)
        
    @staticmethod
    @league_category_bp.put('/<league_category_id>')
    async def update_league_category(league_category_id: str):
        data = await request.get_json()
        try:
            async with AsyncSession() as session:
                category = await session.get(LeagueCategoryModel, league_category_id)
                if not category:
                    raise ApiException("Category not found", 404)
                
                category.copy_with(**data)
                await session.commit()
                
            return await ApiResponse.success(message="Update success")
        
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            return await ApiResponse.error(f"Error: {str(e)}")
        except Exception as e:
            return await ApiResponse.error(e)