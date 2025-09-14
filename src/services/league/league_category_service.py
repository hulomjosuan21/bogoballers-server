from typing import List
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from src.models.team import LeagueTeamModel
from src.extensions import AsyncSession
from src.models.league import LeagueCategoryModel
from src.utils.api_response import ApiException

class LeagueCategoryService:
    @staticmethod
    async def get_eligible_teams(
        session,
        league_category_id: str
    ) -> List[LeagueTeamModel]:
        team_query = await session.execute(
            select(LeagueTeamModel).where(
                LeagueTeamModel.league_category_id == league_category_id,
                LeagueTeamModel.status == "Accepted",
                LeagueTeamModel.is_eliminated.is_(False)
            )
        )
        return team_query.scalars().all()
    
    async def get_category_metadata(self, league_id: str):
        async with AsyncSession() as session:
            result = await session.execute(
                select(LeagueCategoryModel)
                .options(joinedload(LeagueCategoryModel.rounds))
                .where(LeagueCategoryModel.league_id == league_id)
            )
            categories = result.unique().scalars().all()

            metadata_array = []
            for category in categories:
                teams = await LeagueCategoryService.get_eligible_teams(session, category.league_category_id)
                metadata_array.append({
                    'league_category_id': category.league_category_id,
                    'eligible_teams_count': len(teams),
                })

            return metadata_array

    
    async def get_many(self, league_id: str, data: dict):
        if not league_id:
            raise ApiException("No league id.")
        
        async with AsyncSession() as session:
            conditions = [LeagueCategoryModel.league_id == league_id]
            
            result = await session.execute(
                select(LeagueCategoryModel)
                .options(
                    joinedload(LeagueCategoryModel.rounds),
                )
                .where(*conditions)
            )

            categories = result.unique().scalars().all()
            return categories

    async def delet_one(self, league_category_id: str):
        async with AsyncSession() as session:
            try:
                category = await session.get(LeagueCategoryModel, league_category_id)

                if not category:
                    raise ApiException("Category not found.", 404)

                await session.delete(category)
                await session.commit()
                
                return "Category deleted successfully"
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e 

    async def edit_one(self, league_category_id: str, data: dict):
        async with AsyncSession() as session:
            try:
                category = await session.get(LeagueCategoryModel, league_category_id)
                if not category:
                    raise ApiException("Category not found", 404)
                
                category.copy_with(**data)
                await session.commit()
                
                return "Update success"
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e