from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload
from src.extensions import AsyncSession
from src.models.league import LeagueCategoryModel, LeagueCategoryRoundModel
from src.utils.api_response import ApiException

class LeagueCategoryService:
    async def save_changes(self, league_category_id: str, operations: list):
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
            
            return f"Successfully processed {len(results)} operations", results

    async def update_round_format(self, league_category_id: str, round_id: str, round_format: str):
        async with AsyncSession() as session:
            result = await session.execute(
                select(LeagueCategoryRoundModel)
                .where(LeagueCategoryRoundModel.league_category_id == league_category_id)
                .where(LeagueCategoryRoundModel.round_id == round_id)
            )
            round_obj = result.scalar_one_or_none()

            if not round_obj:
                raise ApiException("Round not found")

            round_obj.round_format = round_format
            await session.commit()
            await session.refresh(round_obj)

            return "Round format updated successfully", {
                "round_id": round_obj.round_id, 
                "round_format": round_obj.round_format
            }

    async def add_league_category(self, league_id: str, category_ids: list):
        if not category_ids or not isinstance(category_ids, list):
            raise ApiException("Request body must be a non-empty list of category IDs")
        if any(not cid for cid in category_ids):
            raise ApiException("All category IDs must be valid non-empty strings")

        async with AsyncSession() as session:
            try:
                for category_id in category_ids:
                    new_category = LeagueCategoryModel(
                        league_id=league_id,
                        category_id=category_id,
                    )
                    session.add(new_category)

                await session.commit()
                return "Categories added successfully"
            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise

    async def get_league_categories(self, league_id: str):
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
            return [c.to_json() for c in categories]

    async def delete_league_category(self, league_category_id: str):
        async with AsyncSession() as session:
            try:
                category = await session.get(LeagueCategoryModel, league_category_id)

                if not category:
                    raise ApiException("Category not found.", 404)

                await session.delete(category)
                await session.commit()
                
                return "Category deleted successfully"
            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise

    async def update_league_category(self, league_category_id: str, data: dict):
        async with AsyncSession() as session:
            try:
                category = await session.get(LeagueCategoryModel, league_category_id)
                if not category:
                    raise ApiException("Category not found", 404)
                
                category.copy_with(**data)
                await session.commit()
                
                return "Update success"
            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise