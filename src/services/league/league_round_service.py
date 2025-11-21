from dataclasses import asdict
import json
from typing import List
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.models.match import LeagueMatchModel
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
   