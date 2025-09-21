from dataclasses import asdict
import json
from typing import List
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.services.match.match_service import LeagueMatchService
from src.services.league.league_team_service import LeagueTeamService
from src.engines.match_generation_engine import MatchGenerationEngine
from src.models.match import LeagueMatchModel
from src.models.match_types import parse_round_config
from src.services.league.league_category_service import LeagueCategoryService
from src.models.league import LeagueCategoryRoundModel
from src.extensions import AsyncSession
from src.utils.api_response import ApiException
from enum import Enum

class RoundStateEnum(str, Enum):
    Upcoming = "Upcoming"
    Ongoing = "Ongoing"
    Finished = "Finished"

class LeagueRoundService:
    async def get_matches_for_round(self, session, round_id: str) -> List[LeagueMatchModel]:
        result = await session.execute(
            select(LeagueMatchModel)
            .where(LeagueMatchModel.round_id == round_id)
        )
        return result.scalars().all()
    
    async def progress_double_elim_stage(self, league_id: str, round_id: str) -> List[LeagueMatchModel]:
        async with AsyncSession() as session:
            round_model = await session.get(LeagueCategoryRoundModel, round_id)
            if not round_model:
                raise ValueError(f"Round not found: {round_id}")

            config = parse_round_config(round_model.format_config)
            current_stage = config.progress_group
            max_stage = config.max_progress_group

            if current_stage > max_stage:
                return []

            teams = await LeagueCategoryService.get_eligible_teams(session, round_model.league_category_id)
            matches = await self.get_matches_for_round(session, round_id)

            round_model.matches = matches

            generator = MatchGenerationEngine(league_id, round_model, teams)
            new_matches = await generator.generate_double_elim_stage(session, current_stage)

            session.add_all(new_matches)
            
            for team in teams:
                loss_count = await LeagueMatchService.get_team_loss_count(session, team.league_team_id)
                if loss_count >= config.max_loss:
                    team.is_eliminated = True
                    session.add(team)


            config.progress_group = current_stage + 1
            round_model.format_config = asdict(config)

            await session.commit()
            return new_matches 
    
    async def update_one(self, round_id: str, data: dict):
        try:
            async with AsyncSession() as session:
                round_obj = await session.get(LeagueCategoryRoundModel, round_id)
                if not round_obj:
                    raise ApiException("No category round found")
                
                round_obj.copy_with(**data)
                await session.commit()
                
            return "Round config successfully."
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e
        
    async def round_progression(self, round_id: str, data: dict):
        try:
            round_status = data.get("round_status")
            auto_proceed = bool(data.get("auto_proceed", False))

            async with AsyncSession() as session:
                round_obj = await session.get(LeagueCategoryRoundModel, round_id)
                
                if not round_obj.format_type and not round_obj.format_config and round_status == RoundStateEnum.Ongoing:
                    raise ApiException("Unable to start round: format config is not set")

                next_round_obj = None
                if round_obj.next_round_id:
                    next_round_obj = await session.get(
                        LeagueCategoryRoundModel, round_obj.next_round_id
                    )
                prev_round_obj = None
                stmt = select(LeagueCategoryRoundModel).where(
                    LeagueCategoryRoundModel.next_round_id == round_obj.round_id
                )
                result = await session.execute(stmt)
                prev_round_obj = result.scalars().first()
                
                if round_status == RoundStateEnum.Finished:
                    round_obj.round_status = RoundStateEnum.Finished
                    if auto_proceed and next_round_obj:
                        next_round_obj.round_status = RoundStateEnum.Ongoing

                elif round_status == RoundStateEnum.Ongoing:
                    round_obj.round_status = RoundStateEnum.Ongoing
    
                elif round_status == RoundStateEnum.Upcoming:
                    round_obj.round_status = RoundStateEnum.Upcoming
                    if auto_proceed:
                        if prev_round_obj:
                            prev_round_obj.round_status = RoundStateEnum.Ongoing
                        if next_round_obj:
                            next_round_obj.round_status = RoundStateEnum.Upcoming

                await session.commit()

            return "Round progress updated successfully"

        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e
        
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
                        next_round_id=op_data.get("next_round_id"),
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
                    
                    round_obj = await session.get(LeagueCategoryRoundModel, round_id)
                          
                    if round_obj:
                        round_obj.position = position
                        results.append({
                            "operation": "update_position",
                            "round_id": round_id,
                            "status": "success"
                        })
                
                elif op_type == "update_format":
                    round_id = op_data.get("round_id")
                    round_format = op_data.get("round_format", None)
                    format_type = round_format.get('format_type', None)
                    format_config = round_format.get('format_config', None)
                    rount_order = round_format.get('round_order', 0)
                    round_status = round_format.get('round_status')
                    
                    if round_status in (RoundStateEnum.Finished, RoundStateEnum.Ongoing):
                        raise ApiException(
                            f"Unable to update format: round already {round_status.lower()}"
                        )
           
                    if rount_order < 3 and format_type == "TwiceToBeat":
                        raise ApiException("Twice to beat format only for final round")
         
                    if not round_id:
                        continue
                    
                    round_obj = await session.get(LeagueCategoryRoundModel, round_id)
                    
                    if round_obj:
                        round_obj.round_format = round_format
                        round_obj.format_type = format_type
                        round_obj.format_config = format_config
                        
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
                    
                    round_obj = await session.get(LeagueCategoryRoundModel, round_id)
                    
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
                    
                    round_obj = await session.get(LeagueCategoryRoundModel, round_id)
                    
                    if round_obj:
                        await session.execute(
                            update(LeagueCategoryRoundModel)
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