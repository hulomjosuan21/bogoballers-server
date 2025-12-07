from typing import Any, Dict, List
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from src.models.category import CategoryModel
from src.models.league_admin import LeagueAdministratorModel
from src.models.group import LeagueGroupModel
from src.models.match import LeagueMatchModel
from src.models.team import LeagueTeamModel
from src.extensions import AsyncSession
from src.models.league import LeagueCategoryModel, LeagueCategoryRoundModel, LeagueModel
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
            
    async def get_category_round_group_names(self, user_id, public_league_id: str | None):
        async with AsyncSession() as session:
            stmt_league = select(LeagueModel.league_id, LeagueModel.status)

            if public_league_id:
                stmt_league = stmt_league.where(LeagueModel.public_league_id == public_league_id)
            else:
                stmt_league = (
                    stmt_league
                    .join(LeagueModel.creator)
                    .where(
                        LeagueAdministratorModel.user_id == user_id,
                        LeagueModel.status.in_(["Pending", "Scheduled", "Ongoing"])
                    )
                )

            result_league = await session.execute(stmt_league)
            league_row = result_league.first() 

            if not league_row:
                raise ApiException("League not found", 404)

            target_league_id = league_row.league_id
            target_league_status = league_row.status

         
            stmt_cats = (
                select(
                    LeagueCategoryModel.league_category_id,
                    CategoryModel.category_name
                )
                .join(LeagueCategoryModel.category)
                .where(LeagueCategoryModel.league_id == target_league_id)
            )
            
            cats_result = await session.execute(stmt_cats)
            cats_rows = cats_result.all()

            if not cats_rows:
                return {
                    "league_id": target_league_id,
                    "league_status": target_league_status,
                    "payload": []
                }


            cat_ids = [row.league_category_id for row in cats_rows]

            stmt_rounds = (
                select(
                    LeagueCategoryRoundModel.round_id,
                    LeagueCategoryRoundModel.round_name,
                    LeagueCategoryRoundModel.league_category_id
                )
                .where(LeagueCategoryRoundModel.league_category_id.in_(cat_ids))
                .order_by(LeagueCategoryRoundModel.round_order.asc())
            )

            rounds_result = await session.execute(stmt_rounds)
            rounds_rows = rounds_result.all()

            round_ids = [row.round_id for row in rounds_rows]
            
            groups_rows = []
            if round_ids:
                stmt_groups = (
                    select(
                        LeagueGroupModel.group_id,
                        LeagueGroupModel.display_name,
                        LeagueGroupModel.round_id
                    )
                    .where(LeagueGroupModel.round_id.in_(round_ids))
                )
                groups_result = await session.execute(stmt_groups)
                groups_rows = groups_result.all()

            groups_map = {}
            for g_row in groups_rows:
                r_id = g_row.round_id
                if r_id not in groups_map:
                    groups_map[r_id] = []
                groups_map[r_id].append({
                    "group_id": g_row.group_id, 
                    "group_name": g_row.display_name
                })

            rounds_map = {}
            for r_row in rounds_rows:
                c_id = r_row.league_category_id
                if c_id not in rounds_map:
                    rounds_map[c_id] = []
                
                rounds_map[c_id].append({
                    "round_id": r_row.round_id,
                    "round_name": r_row.round_name,
                    "groups": groups_map.get(r_row.round_id, [])
                })
            payload = []
            for c_row in cats_rows:
                payload.append({
                    "league_category_id": c_row.league_category_id,
                    "category_name": c_row.category_name,
                    "rounds": rounds_map.get(c_row.league_category_id, [])
                })

            return {
                "league_id": target_league_id,
                "league_status": target_league_status,
                "payload": payload,
            }