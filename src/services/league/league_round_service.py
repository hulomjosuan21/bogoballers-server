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
        