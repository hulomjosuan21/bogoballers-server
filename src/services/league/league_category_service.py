from typing import Dict, List
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from src.models.group import LeagueGroupModel
from src.models.match import LeagueMatchModel
from src.models.team import LeagueTeamModel
from src.extensions import AsyncSession
from src.models.league import LeagueCategoryModel, LeagueCategoryRoundModel
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
                LeagueTeamModel.is_eliminated.is_(False),
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
            
            
            if data:
                if data.get('condition') == "Automatic":
                    conditions.append(LeagueCategoryModel.manage_automatic.is_(True))
                if data.get('condition') == "Manual":
                    conditions.append(LeagueCategoryModel.manage_automatic.is_(False))
            
            stmt = select(LeagueCategoryModel).where(*conditions)
            
            result = await session.execute(stmt)

            categories = result.scalars().all()
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
            
    async def edit_many(self, updates: List[Dict]):
        async with AsyncSession() as session:
            try:
                for update in updates:
                    league_category_id = update.pop("league_category_id", None)
                    if not league_category_id:
                        continue
                    
                    category = await session.get(LeagueCategoryModel, league_category_id)
                    if not category:
                        continue 

                    result = await session.execute(
                        select(LeagueMatchModel)
                        .where(LeagueMatchModel.league_category_id == league_category_id)
                    )
                    started_matches = result.scalars().all()

                    for key, value in update.items():
                        if started_matches and key in ["max_team", "manage_automatic"]:
                            raise ApiException(f"Cannot update because matches have already started")
                        
                        setattr(category, key, value)

                await session.commit()
                return f"Changes {len(updates)}"

            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e
            
    async def get_category_round_group_names(self, league_id: str):
        async with AsyncSession() as session:
            stmt = (
                select(LeagueCategoryModel)
                .options(
                    joinedload(LeagueCategoryModel.rounds).joinedload(LeagueCategoryRoundModel.format),
                    joinedload(LeagueCategoryModel.rounds).joinedload(LeagueCategoryRoundModel.format),
                    joinedload(LeagueCategoryModel.rounds).joinedload(LeagueCategoryRoundModel.format),
                )
                .where(LeagueCategoryModel.league_id == league_id)
            )

            result = await session.execute(stmt)
            categories = result.unique().scalars().all()

            data = []
            for category in categories:
                rounds_data = []
                for round_ in category.rounds:
                    group_result = await session.execute(
                        select(LeagueGroupModel).where(
                            LeagueGroupModel.league_category_id == category.league_category_id,
                            LeagueGroupModel.round_id == round_.round_id,
                        )
                    )
                    groups = group_result.scalars().all()

                    rounds_data.append({
                        "round_id": round_.round_id,
                        "round_name": round_.round_name,
                        "groups": [
                            {"group_id": g.group_id, "group_name": g.display_name}
                            for g in groups
                        ]
                    })

                data.append({
                    "league_category_id": category.league_category_id,
                    "category_name": category.category.category_name,
                    "rounds": rounds_data,
                })

            return data