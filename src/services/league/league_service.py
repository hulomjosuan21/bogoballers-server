import json
from datetime import datetime
import re
from dateutil.relativedelta import relativedelta
from sqlalchemy import  Date,Text, and_, case, cast, func, or_, select
from src.services.league_admin_service import LeagueAdministratorService
from src.models.player import LeaguePlayerModel
from src.models.team import LeagueTeamModel
from src.models.league_admin import LeagueAdministratorModel
from src.models.league import LeagueModel, LeagueCategoryModel
from src.services.cloudinary_service import CloudinaryService
from src.extensions import AsyncSession, settings
from src.utils.api_response import ApiException, ApiResponse
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.exc import NoResultFound
from src.utils.server_utils import validate_required_fields

ALLOWED_OPTION_KEYS = {
    "player_residency_certificate_required",
    "player_residency_certificate_valid_until"
}

league_admin_service = LeagueAdministratorService()

class LeagueService:
    async def analytics(self, league_id: str):
        async with AsyncSession() as session:
            stmt_league = (
                select(LeagueModel)
                .options(
                    selectinload(LeagueModel.categories).selectinload(LeagueCategoryModel.rounds),
                    selectinload(LeagueModel.categories).selectinload(LeagueCategoryModel.teams)
                )
                .where(
                    LeagueModel.league_id == league_id,
                    LeagueModel.status.in_(["Scheduled", "Ongoing"])
                )
            )
            result = await session.execute(stmt_league)
            active_league = result.scalar_one_or_none()
            
            if not active_league:
                raise ApiException("No found league.")
            stmt_teams = (
                select(
                    func.count(LeagueTeamModel.league_team_id).label("team_count"),
                    func.max(LeagueTeamModel.updated_at).label("last_update")
                )
                .where(
                    LeagueTeamModel.league_id == active_league.league_id,
                    LeagueTeamModel.status == "Accepted",
                    LeagueTeamModel.payment_status.in_(["Paid Online", "Paid On Site", "Waived"]),
                )
            )
            result_teams = await session.execute(stmt_teams)
            team_stats = result_teams.one()
            total_accepted_teams = team_stats.team_count
            teams_last_update = team_stats.last_update.isoformat() if team_stats.last_update else None

            stmt_profit = (
                select(
                    func.coalesce(func.sum(LeagueTeamModel.amount_paid), 0).label("total_profit"),
                    func.max(LeagueTeamModel.updated_at).label("last_update")
                )
                .where(
                    LeagueTeamModel.league_id == active_league.league_id,
                    LeagueTeamModel.status == "Accepted",
                    LeagueTeamModel.payment_status.in_(["Paid Online", "Paid On Site", "Waived"]),
                )
            )
            result_profit = await session.execute(stmt_profit)
            profit_stats = result_profit.one()
            total_profit = profit_stats.total_profit
            profit_last_update = profit_stats.last_update.isoformat() if profit_stats.last_update else None

            stmt_profit_chart = (
                select(
                    cast(LeagueTeamModel.updated_at, Date).label("date"),
                    func.coalesce(func.sum(LeagueTeamModel.amount_paid), 0).label("amount")
                )
                .where(
                    LeagueTeamModel.league_id == active_league.league_id,
                    LeagueTeamModel.status == "Accepted",
                    LeagueTeamModel.payment_status.in_(["Paid Online", "Paid On Site", "Waived"]),
                )
                .group_by(cast(LeagueTeamModel.updated_at, Date))
                .order_by(cast(LeagueTeamModel.updated_at, Date))
            )
            result_chart = await session.execute(stmt_profit_chart)
            profit_chart = [
                {"date": row.date.isoformat(), "amount": float(row.amount)}
                for row in result_chart.all()
            ]

            stmt_players = (
                select(
                    func.count(LeaguePlayerModel.league_player_id).label("player_count"),
                    func.max(LeaguePlayerModel.updated_at).label("last_update")
                )
                .where(LeaguePlayerModel.league_id == active_league.league_id)
            )
            result_players = await session.execute(stmt_players)
            player_stats = result_players.one()
            total_players = player_stats.player_count
            players_last_update = player_stats.last_update.isoformat() if player_stats.last_update else None

            stmt_categories = (
                select(
                    func.count(LeagueCategoryModel.league_category_id).label("category_count"),
                    func.max(LeagueCategoryModel.updated_at).label("last_update")
                )
                .where(LeagueCategoryModel.league_id == active_league.league_id)
            )
            result_categories = await session.execute(stmt_categories)
            category_stats = result_categories.one()
            total_categories = category_stats.category_count
            categories_last_update = category_stats.last_update.isoformat() if category_stats.last_update else None

            return {
                "active_league": active_league.to_json_for_analytics(),
                "total_accepted_teams": {
                    "count": total_accepted_teams,
                    "last_update": teams_last_update,
                },
                "total_categories": {
                    "count": total_categories,
                    "last_update": categories_last_update,
                },
                "total_profit": {
                    "amount": total_profit,
                    "last_update": profit_last_update,
                    "chart": profit_chart,
                },
                "total_players": {
                    "count": total_players,
                    "last_update": players_last_update,
                },
            }
        
    async def search_leagues(self, session, search: str, limit: int = 10) -> list[LeagueModel]:
        search_term = f"%{search}%"
        search_lower = search.lower()

        query = (
            select(LeagueModel)
            .options(
                selectinload(LeagueModel.creator).selectinload(LeagueAdministratorModel.user),
                selectinload(LeagueModel.categories).selectinload(LeagueCategoryModel.rounds),
            )
            .where(
                or_(
                    func.lower(LeagueModel.league_title).like(func.lower(search_term)),
                    func.lower(LeagueModel.league_address).like(func.lower(search_term)),
                    cast(LeagueModel.status, Text).ilike(search_term)
                )
            )
            .order_by(
                case(
                    (func.lower(LeagueModel.league_title) == search_lower, 1),
                    (cast(LeagueModel.status, Text).ilike(search), 2),
                    else_=3
                ),
                LeagueModel.league_title
            )
            .limit(limit)
        )

        result = await session.execute(query)
        leagues = result.scalars().unique().all()
        return leagues

    async def create_one(self, user_id, form_data: dict, files: dict):
        required_fields = [
            "league_title", "league_budget", "league_description", "league_address", "sportsmanship_rules",
            "registration_deadline", "opening_date", "league_schedule", "banner_image", "categories"
        ]
        try:
            validate_required_fields(form_data, required_fields)
            league_title=form_data['league_title'],
            
            sportsmanship_rules = json.loads(form_data['sportsmanship_rules'])
            categories = json.loads(form_data['categories'])

            registration_deadline = datetime.fromisoformat(form_data['registration_deadline'].replace("Z", "+00:00"))
            opening_date = datetime.fromisoformat(form_data['opening_date'].replace("Z", "+00:00"))

            banner_file = files.get("banner_image")
            banner_image_url = form_data.get("banner_image")
            
            if banner_file:
                banner_url = await CloudinaryService.upload_file(banner_file, folder=settings["league_banners_folder"])
            elif banner_image_url and re.match(r'^https?://', banner_image_url):
                banner_url = banner_image_url
            else:
                raise ApiException("Invalid or missing banner image")

            async with AsyncSession() as session:
                league_admin = await league_admin_service.get_one(session=session,user_id=user_id)
                if not league_admin:
                    raise ApiException("League administrator not found", 404)

                league_schedule = tuple(datetime.fromisoformat(d[:10]).date() for d in json.loads(form_data['league_schedule']))

                new_league = LeagueModel(
                    league_administrator_id=league_admin.league_administrator_id,
                    league_title=league_title,
                    league_budget=float(form_data['league_budget']),
                    league_description=form_data['league_description'],
                    league_address=form_data['league_address'],
                    registration_deadline=registration_deadline,
                    opening_date=opening_date,
                    league_schedule=league_schedule,
                    banner_url=banner_url,
                    sportsmanship_rules=sportsmanship_rules,
                    league_courts=[],
                    league_officials=[],
                    league_referees=[],
                    league_affiliates=[],
                    categories=[
                        LeagueCategoryModel(
                            category_id=cat_id,
                        ) for cat_id in categories
                    ]
                )

                session.add(new_league)
                await session.commit()
                return f"League {league_title} as been create new start managing you league categories"
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e 
        
    async def _get_one(self):
        return (
            select(LeagueModel)
            .options(
                joinedload(LeagueModel.creator).joinedload(LeagueAdministratorModel.account),
                selectinload(LeagueModel.categories)
                    .joinedload(LeagueCategoryModel.category)
                    .selectinload(LeagueCategoryModel.rounds)
            )
        )
        
    async def get_one(self, league_administrator_id: str, data: dict):
        async with AsyncSession() as session:
            conditions = [LeagueModel.league_administrator_id == league_administrator_id]
            
            if data.get('status'):
                conditions.append(LeagueModel.status == data["status"])

            stmt = await self._get_one()
            stmt = stmt.where(and_(*conditions))

            try:
                league = (await session.execute(stmt)).scalar_one()
            except NoResultFound:
                raise ApiException("No League found")

            return league.to_json()
        
    async def edit_one(self, league_id: str, data: dict):
        try:
            async with AsyncSession() as session:
                league_obj = await session.get(LeagueModel, league_id)
                
                if not league_obj:
                    raise ApiException("No League found")
                
                league_obj.copy_with(**data)
                
                await session.commit()
                
                return f"League {league_obj.league_title} edited successfully"
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e 
        
    async def delete_one(self, league_id: str):
        try:
            async with AsyncSession() as session:
                league_obj = await session.get(LeagueModel, league_id)
                
                if not league_obj:
                    raise ApiException("No League found")
                
                await session.delete(league_obj)
                await session.commit()
                
                return f"League {league_obj.league_title} deleted successfully"
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e 