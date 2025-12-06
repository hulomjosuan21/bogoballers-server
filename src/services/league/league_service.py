import io
import json
from datetime import datetime
import os
import platform
import re
import tempfile
from typing import List
import subprocess
from dateutil.relativedelta import relativedelta
from quart import send_file
from sqlalchemy import  Date,Text, and_, case, cast, func, or_, select, update
from src.models.league_log_model import LeagueLogModel
from src.models.match import LeagueMatchModel
from src.services import league_admin_service
from src.models.player import LeaguePlayerModel, PlayerTeamModel
from src.models.team import LeagueTeamModel, TeamModel
from src.models.league_admin import LeagueAdministratorModel
from src.models.league import LeagueModel, LeagueCategoryModel
from src.services.cloudinary_service import CloudinaryService
from src.extensions import LEAGUE_TEMPLATE_PATH, AsyncSession, settings
from src.utils.api_response import ApiException, ApiResponse
from sqlalchemy.orm import selectinload, joinedload, noload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.exc import NoResultFound
from src.utils.server_utils import validate_required_fields
from docxtpl import DocxTemplate
ALLOWED_OPTION_KEYS = {
    "player_residency_certificate_required",
    "player_residency_certificate_valid_until"
}

DATETIME_FORMAT = "%b %d, %Y %I:%M %p" 
DATE_ONLY_FORMAT = "%b %d, %Y"
class LeagueService:
    def format_datetime_with_time(self, date_str):
        try:
            dt_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt_obj.strftime(DATETIME_FORMAT)
        except Exception:
            return date_str

    def format_date_only(self, date_str):
        try:
            dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
            return dt_obj.strftime(DATE_ONLY_FORMAT)
        except Exception:
            return date_str
    
    async def print_league(self, league_id: str):
        async with AsyncSession() as session:

            stmt = (
                select(LeagueModel)
                .where(LeagueModel.league_id == league_id)
                .options(
                    joinedload(LeagueModel.creator).joinedload(LeagueAdministratorModel.account),
                    selectinload(LeagueModel.categories).joinedload(LeagueCategoryModel.category),
                    selectinload(LeagueModel.categories).selectinload(LeagueCategoryModel.rounds),
                    selectinload(LeagueModel.teams).joinedload(LeagueTeamModel.team)
                )
            )

            result = await session.execute(stmt)
            league = result.scalar_one_or_none()

            if not league:
                raise ApiException("League not found")

            data = league.to_json(include_team=True)

        creator = data["creator"]
        admin_account = creator["account"]

        courts_table = [
            {
                "court_name": c.get("name","Unnamed"),
                "location": c.get("location","N/A"),
            }
            for c in data["league_courts"]
        ]

        officials_table = [
            {
                "full_name": o.get("full_name","Unnamed"),
                "role": o.get("role", "N/A"),
                "contact_info": o.get("contact_info","N/A")
            }
            for o in data["league_officials"]
        ]

        referees_table = [
            {
                "full_name": r.get("full_name","Unnamed"),
                "contact_info": r.get("contact_info", "N/A"),
            }
            for r in data["league_referees"]
        ]
        

        affiliates_table = [
            {
                "name": a.get("name", "Unnamed"),
                "value": a.get("value", "N/A"),
                "contact_info": a.get("contact_info", "N/A")
            }
            for a in data["league_affiliates"]
        ]

        categories_table = [
            {
                "category_name": c.get("category_name", "Unnamed Category"),
                "max_team": c.get("max_team", "N/A")
            }
            for c in data["league_categories"]
        ]

        teams_table = [
            {
                "team_name": t.get("team_name", "Unnamed Team"),
                "coach_name": t.get("coach_name", "N/A"),
                "assistant_coach_name": t.get("assistant_coach_name", "N/A")
            }
            for t in data["teams"]
        ]
        
        league_commissioner = next(
            (o["full_name"] for o in data["league_officials"] if o["role"].lower() == "league commissioner"),
            "N/A"
        )

        league_director = next(
            (o["full_name"] for o in data["league_officials"] if o["role"].lower() == "league director"),
            "N/A"
        )

        # ✅ Context matches Docx template
        context = {
            "league_director": league_director,
            "league_commissioner": league_commissioner,
            
            "league_title": data["league_title"],
            "league_description": data["league_description"],
            "league_address": data["league_address"],
            "league_budget": data["league_budget"],
            "registration_deadline": self.format_datetime_with_time(data["registration_deadline"]),
            "opening_date": self.format_datetime_with_time(data["opening_date"]),
            "schedule_start": self.format_date_only(data["league_schedule"][0]),
            "schedule_end": self.format_date_only(data["league_schedule"][1]),
            "season_year": data["season_year"],

            "organization_name": creator["organization_name"],
            "organization_address": creator["organization_address"],
            "organization_email": admin_account["email"],
            "organization_contact": admin_account["contact_number"],

            "courts_table": courts_table,
            "officials_table": officials_table,
            "referees_table": referees_table,
            "affiliates_table": affiliates_table,
            "categories_table": categories_table,
            "teams_table": teams_table,
        }

        # Render Docx
        doc = DocxTemplate(LEAGUE_TEMPLATE_PATH)
        doc.render(context)

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_doc:
            doc.save(tmp_doc.name)
            tmp_doc_path = tmp_doc.name

        # Convert to PDF
        LO_PATH = r"C:\Program Files\LibreOffice\program\soffice.exe" if platform.system() == "Windows" else "libreoffice"
        output_dir = tempfile.gettempdir()

        subprocess.run([
            LO_PATH, "--headless", "--convert-to", "pdf", tmp_doc_path, "--outdir", output_dir
        ], check=True)

        pdf_temp_path = os.path.join(
            output_dir, os.path.basename(tmp_doc_path).replace(".docx", ".pdf")
        )

        with open(pdf_temp_path, "rb") as f:
            pdf_bytes = f.read()

        return await send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            attachment_filename=f"{data['league_title']}_document.pdf"
        )
    
    def _base_stmt(self):
        return (
            select(LeagueModel)
            .options(
                joinedload(LeagueModel.creator).joinedload(LeagueAdministratorModel.account),
                selectinload(LeagueModel.categories).joinedload(LeagueCategoryModel.category),
                selectinload(LeagueModel.categories).selectinload(LeagueCategoryModel.rounds),
            )
        )

    def _get_one_stmt(self):
        return self._base_stmt().limit(1)

    def _get_many_stmt(self):
        return self._base_stmt()
    
    async def fetch_participation(
        self, 
        user_id: str | None = None, 
        player_id: str | None = None
    ):
        async with AsyncSession() as session:

            if player_id:
                result_pt = await session.execute(
                    select(PlayerTeamModel).where(PlayerTeamModel.player_id == player_id)
                )
                pts = result_pt.unique().scalars().all()
                team_ids = [pt.team_id for pt in pts]

                result_lt = await session.execute(
                    select(LeagueTeamModel)
                    .where(LeagueTeamModel.team_id.in_(team_ids))
                    .options(
                        joinedload(LeagueTeamModel.team),
                        joinedload(LeagueTeamModel.league),
                        joinedload(LeagueTeamModel.league_players)
                    )
                )
                league_teams = result_lt.unique().scalars().all()

                response = []

                for lt in league_teams:
                    result_m = await session.execute(
                        select(LeagueMatchModel)
                        .where(
                            (LeagueMatchModel.home_team_id == lt.league_team_id) |
                            (LeagueMatchModel.away_team_id == lt.league_team_id)
                        )
                        .options(
                            joinedload(LeagueMatchModel.home_team).joinedload(LeagueTeamModel.team),
                            joinedload(LeagueMatchModel.away_team).joinedload(LeagueTeamModel.team),
                        )
                    )
                    matches = result_m.unique().scalars().all()

                    response.append({
                        "league": lt.league.to_json(),
                        "teams": [lt.to_json()],
                        "matches": [m.to_json() for m in matches]
                    })

                return response
            
            if user_id:
                result_tm = await session.execute(
                    select(TeamModel).where(TeamModel.user_id == user_id)
                )
                teams = result_tm.unique().scalars().all()
                team_ids = [t.team_id for t in teams]

                result_lt = await session.execute(
                    select(LeagueTeamModel)
                    .where(LeagueTeamModel.team_id.in_(team_ids))
                    .options(
                        joinedload(LeagueTeamModel.team),
                        joinedload(LeagueTeamModel.league),
                        joinedload(LeagueTeamModel.league_players)
                    )
                )
                league_teams = result_lt.unique().scalars().all()

                leagues_dict = {}
                for lt in league_teams:
                    leagues_dict.setdefault(lt.league_id, []).append(lt)

                response = []

                for league_id, lt_list in leagues_dict.items():
                    league_obj = lt_list[0].league
                    lt_ids = [lt.league_team_id for lt in lt_list]

                    result_m = await session.execute(
                        select(LeagueMatchModel)
                        .where(
                            (LeagueMatchModel.home_team_id.in_(lt_ids)) |
                            (LeagueMatchModel.away_team_id.in_(lt_ids))
                        )
                        .options(
                            joinedload(LeagueMatchModel.home_team).joinedload(LeagueTeamModel.team),
                            joinedload(LeagueMatchModel.away_team).joinedload(LeagueTeamModel.team),
                        )
                    )
                    matches = result_m.unique().scalars().all()

                    response.append({
                        "league": league_obj.to_json(),
                        "teams": [lt.to_json() for lt in lt_list],
                        "matches": [m.to_json() for m in matches]
                    })

                return response

            return None

    async def fetch_by_user(user_id: str):
        async with AsyncSession() as session:
            stmt = (
                select(LeagueModel)
                .join(LeagueModel.creator)
                .where(LeagueAdministratorModel.user_id == user_id)
                .limit(1)
            )
            result = await session.execute(stmt) 
            league_obj = result.scalars().first()

            if league_obj:
                return league_obj
            else:
                return None

    async def fetch_by_public_id(self, public_league_id: str):
        async with AsyncSession() as session:
            stmt = (
                select(LeagueModel)
                .where(LeagueModel.public_league_id == public_league_id)
                .limit(1)
                .options(
                    noload(LeagueModel.teams),
                    noload(LeagueModel.league_match_records),
                )
            )
            result = await session.execute(stmt) 
            league_obj = result.scalars().first()

            if league_obj:
                return league_obj
            else:
                return None

    async def fetch_active(self, user_id: str):
        async with AsyncSession() as session:
            active_statuses = ["Pending", "Scheduled", "Ongoing"]

            stmt = (
                select(LeagueModel)
                .join(LeagueModel.creator)
                .where(LeagueAdministratorModel.user_id == user_id)
                .where(LeagueModel.status.in_(active_statuses))
                .limit(1)
                .options(
                    noload(LeagueModel.teams),
                    noload(LeagueModel.league_match_records),
                )
            )
            result = await session.execute(stmt) 
            legue_obj = result.scalars().first()

            if legue_obj:
                return legue_obj
            else:
                return None
        
    async def fetch_records(self, user_id: str):
        async with AsyncSession() as session:
            active_statuses = ["Pending", "Scheduled", "Ongoing"]

            priority_sorting = case(
                (LeagueModel.status.in_(active_statuses), 0),
                else_=1
            )
            stmt = (
                select(LeagueModel)
                .join(LeagueModel.creator)
                .where(LeagueAdministratorModel.user_id == user_id)
                .order_by(
                    priority_sorting.asc(),
                    LeagueModel.league_created_at.desc()
                )
            )
            result = await session.execute(stmt) 
            league_objs = result.scalars().all()
            return [league.to_json(include_team=True,include_record=True) for league in league_objs]
                
    async def fetch_generic(
        self,
        user_id,
        param_public_league_id: str | None,
        param_status_list: list[str],
        param_filter: str | None,
        param_all: bool,
        param_active: bool
    ):
        async with AsyncSession() as session:
            
            if param_filter == 'public' and param_public_league_id is not None:
                stmt = (
                    self._get_one_stmt()
                    .where(LeagueModel.public_league_id == param_public_league_id)
                )
                result = await session.execute(stmt)
                league = result.scalar_one_or_none()
                return league.to_json(include_team=False) if league else None

            from src.services.league_admin_service import LeagueAdministratorService
            league_admin_service = LeagueAdministratorService()

            league_admin = await league_admin_service.get_one(session=session, user_id=user_id)
            if not league_admin:
                raise ApiException("LeagueAdmin not found")

            conditions = []

            if param_active is True:
                active_statuses = ('Pending', 'Scheduled', 'Ongoing')
                conditions.extend([
                    LeagueModel.status.in_(active_statuses),
                    LeagueModel.league_administrator_id == league_admin.league_administrator_id
                ])

                stmt = self._get_one_stmt().where(and_(*conditions))
                result = await session.execute(stmt)
                league = result.scalar_one_or_none()
                return league.to_json() if league else None

            elif param_all is True and param_filter == 'record':
                active_statuses = ('Pending', 'Scheduled', 'Ongoing')
                is_active_case = case(
                    (LeagueModel.status.in_(active_statuses), 0),
                    else_=1
                )

                if param_status_list:
                    conditions.extend([
                        LeagueModel.status.in_(param_status_list),
                        LeagueModel.league_administrator_id == league_admin.league_administrator_id
                    ])

                stmt = (
                    self._get_many_stmt()
                    .where(and_(*conditions))
                    .order_by(
                        is_active_case.asc(),
                        LeagueModel.opening_date.desc()
                    )
                )

                result = await session.execute(stmt)
                leagues = result.scalars().all()
                return [league.to_json(include_team=True) for league in leagues]

            else:
                conditions.append(LeagueModel.league_administrator_id == league_admin.league_administrator_id)
                stmt = self._get_one_stmt().where(and_(*conditions))
                result = await session.execute(stmt)
                league = result.scalar_one_or_none()
                return league.to_json() if league else None

    async def fetch_carousel(self):
        conditions = []
        async with AsyncSession() as session:
            conditions.append(LeagueModel.status.in_(['Pending', 'Scheduled']))

            stmt = (
                self._get_many_stmt()
                .where(and_(*conditions))
                .order_by(
                    LeagueModel.opening_date.desc()
                )
            )

            result = await session.execute(stmt)
            leagues = result.scalars().all()
            return [league.to_json(include_team=True) for league in leagues]
    

    async def analytics(self, league_id: str):
        async with AsyncSession() as session:
            stmt_check = (
                select(LeagueModel.league_id)
                .where(
                    LeagueModel.league_id == league_id,
                    LeagueModel.status.in_(["Pending", "Scheduled", "Ongoing"])
                )
            )
            result = await session.execute(stmt_check)
            if not result.scalar_one_or_none():
                raise ApiException("No found league.")
            team_filter = [
                LeagueTeamModel.league_id == league_id,
                LeagueTeamModel.status == "Accepted",
                LeagueTeamModel.payment_status.notin_(["Pending"])
            ]
            
            profit_filter = [
                LeagueTeamModel.league_id == league_id,
                LeagueTeamModel.status == "Accepted",
                LeagueTeamModel.payment_status.notin_(["Pending", "No Charge", "Refunded"])
            ]
            sq_team_count = select(func.count(LeagueTeamModel.league_team_id)).where(*team_filter).scalar_subquery()
            sq_team_max = select(func.max(LeagueTeamModel.league_team_updated_at)).where(*team_filter).scalar_subquery()
            sq_profit_sum = select(func.coalesce(func.sum(LeagueTeamModel.amount_paid), 0)).where(*profit_filter).scalar_subquery()
            sq_profit_max = select(func.max(LeagueTeamModel.league_team_updated_at)).where(*profit_filter).scalar_subquery()
            sq_player_count = select(func.count(LeaguePlayerModel.league_player_id))\
                .where(LeaguePlayerModel.league_id == league_id).scalar_subquery()
            sq_player_max = select(func.max(LeaguePlayerModel.league_player_updated_at))\
                .where(LeaguePlayerModel.league_id == league_id).scalar_subquery()
            sq_cat_count = select(func.count(LeagueCategoryModel.league_category_id))\
                .where(LeagueCategoryModel.league_id == league_id).scalar_subquery()
            sq_cat_max = select(func.max(LeagueCategoryModel.league_category_updated_at))\
                .where(LeagueCategoryModel.league_id == league_id).scalar_subquery()
            stmt_master_stats = select(
                sq_team_count.label("team_count"),
                sq_team_max.label("team_last_update"),
                sq_profit_sum.label("total_profit"),
                sq_profit_max.label("profit_last_update"),
                sq_player_count.label("player_count"),
                sq_player_max.label("player_last_update"),
                sq_cat_count.label("cat_count"),
                sq_cat_max.label("cat_last_update"),
            )
            
            stats_result = (await session.execute(stmt_master_stats)).one()
            profit_date_expr = cast(func.timezone('UTC', LeagueTeamModel.league_team_updated_at), Date)
            stmt_profit_chart = (
                select(
                    profit_date_expr.label("date"),
                    func.coalesce(func.sum(LeagueTeamModel.amount_paid), 0).label("amount")
                )
                .where(*profit_filter)
                .group_by(profit_date_expr)
                .order_by(profit_date_expr)
            )
            match_date_expr = cast(func.timezone('UTC', LeagueMatchModel.scheduled_date), Date)
            stmt_matches_chart = (
                select(
                    match_date_expr.label("date"),
                    func.count(LeagueMatchModel.league_match_id).label("count")
                )
                .where(
                    LeagueMatchModel.league_id == league_id,
                    LeagueMatchModel.scheduled_date.is_not(None)
                )
                .group_by(match_date_expr)
                .order_by(match_date_expr)
            )

            result_profit_chart = await session.execute(stmt_profit_chart)
            result_matches_chart = await session.execute(stmt_matches_chart)

            profit_chart = [
                {"date": row.date.isoformat(), "amount": float(row.amount)}
                for row in result_profit_chart.all()
            ]

            matches_rows = result_matches_chart.all()
            matches_chart_list = [
                {"date": row.date.isoformat(), "count": row.count}
                for row in matches_rows
            ]

            total_matches_days = 0
            last_match_date_str = None

            if matches_rows:
                start_date = matches_rows[0].date
                end_date = matches_rows[-1].date
                last_match_date_str = end_date.isoformat()
                total_matches_days = (end_date - start_date).days + 1

            return {
                "total_accepted_teams": {
                    "count": stats_result.team_count or 0,
                    "last_update": stats_result.team_last_update.isoformat() if stats_result.team_last_update else None,
                },
                "total_categories": {
                    "count": stats_result.cat_count or 0,
                    "last_update": stats_result.cat_last_update.isoformat() if stats_result.cat_last_update else None,
                },
                "total_profit": {
                    "amount": stats_result.total_profit or 0,
                    "last_update": stats_result.profit_last_update.isoformat() if stats_result.profit_last_update else None,
                    "chart": profit_chart,
                },
                "total_players": {
                    "count": stats_result.player_count or 0,
                    "last_update": stats_result.player_last_update.isoformat() if stats_result.player_last_update else None,
                },
                "matches_chart_data": {
                    "chart": matches_chart_list,
                    "total_days": total_matches_days,
                    "last_match_date": last_match_date_str
                }
            }
        
    async def search_leagues(self, session, search: str, limit: int = 10) -> list[LeagueModel]:
        search_term = f"%{search}%"
        search_lower = search.lower()

        query = (
            select(LeagueModel)
            .options(
                joinedload(LeagueModel.creator).joinedload(LeagueAdministratorModel.account),
                selectinload(LeagueModel.categories)
                    .joinedload(LeagueCategoryModel.category),
                selectinload(LeagueModel.categories)
                    .selectinload(LeagueCategoryModel.rounds),
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

    async def update_league_resource(self, league_id: str, field_name: str, json_data: str, files: dict):
        IMAGE_KEYS = {
            "league_courts": None,
            "league_officials": "photo",
            "league_referees": "photo",
            "league_affiliates": "image"
        }

        if field_name not in IMAGE_KEYS:
            raise ApiException("Invalid field name")

        if not json_data:
            raise ApiException(f"Field '{field_name}' data required")

        try:
            items = json.loads(json_data)
        except json.JSONDecodeError:
            raise ApiException(f"Invalid JSON for '{field_name}'")

        image_key = IMAGE_KEYS[field_name]
        if image_key:
            for idx, item in enumerate(items):
                file_key = f"{field_name}_file_{idx}"
                if file_key in files:
                    file = files[file_key]
                    cloud_url = await CloudinaryService.upload_file(
                        file, folder=f"{field_name}/{league_id}"
                    )
                    item[image_key] = cloud_url

        async with AsyncSession() as session:
            stmt = (
                update(LeagueModel)
                .where(LeagueModel.league_id == league_id)
                .values({field_name: items})
            )
            await session.execute(stmt)
            await session.commit()

        return f"{field_name} updated"

    async def create_one(self, user_id, form_data: dict, files: dict):
        from src.services.league_admin_service import LeagueAdministratorService
        league_admin_service = LeagueAdministratorService()
        
        required_fields = [
            "league_title", "league_budget", "league_description", "league_address", "sportsmanship_rules",
            "registration_deadline", "opening_date", "league_schedule", "banner_image", "categories"
        ]
        try:
            validate_required_fields(form_data, required_fields)
            league_title=form_data['league_title']
            
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
                # load categories
                selectinload(LeagueModel.categories)
                    .joinedload(LeagueCategoryModel.category),
                # load rounds (separate path)
                selectinload(LeagueModel.categories)
                    .selectinload(LeagueCategoryModel.rounds),
            )
        )
        
    async def get_one_by_public_id(self, public_league_id: str, data: dict):
        async with AsyncSession() as session:
            conditions = [LeagueModel.public_league_id == public_league_id]
            
            if data:
                condition = data.get('condition')
                
                if condition == 'Active':
                    conditions.extend([~LeagueModel.status.in_(["Cancelled", "Postponed", "Completed"])])
            
            stmt = select(LeagueModel).where(*conditions)
            
            result = await session.execute(stmt)
            
            league = result.scalar_one_or_none()
            
            if not league:
                raise ApiException('No league found')
            
            return league
        
    @staticmethod
    async def get_one_active(session, league_administrator_id: str, data: dict):
        conditions = [LeagueModel.league_administrator_id == league_administrator_id]

        condition = data.get("condition")
        if condition == "Active":
            conditions.append(
                ~LeagueModel.status.in_(["Cancelled", "Postponed", "Completed"])
            )
            
        league_service = LeagueService()

        stmt = await league_service._get_one()
        stmt = stmt.where(and_(*conditions))

        league = (await session.execute(stmt)).scalar_one_or_none()
        return league
        
    async def edit_one(self, league_id: str, data: dict):
        try:
            async with AsyncSession() as session:
                league_obj = await session.get(LeagueModel, league_id)
                
                if not league_obj:
                    raise ApiException("No League found")
                
                processed_data = data.copy()
                if 'registration_deadline' in processed_data and processed_data['registration_deadline']:
                    processed_data['registration_deadline'] = datetime.fromisoformat(
                        processed_data['registration_deadline'].replace('Z', '+00:00')
                    )
                if 'opening_date' in processed_data and processed_data['opening_date']:
                    processed_data['opening_date'] = datetime.fromisoformat(
                        processed_data['opening_date'].replace('Z', '+00:00')
                    )
                
                league_obj.copy_with(**processed_data)
                
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

    async def get_logs(self, league_id: str = None, round_id: str = None, team_id: str = None, limit: int = 100):
        async with AsyncSession() as session:
            stmt = select(LeagueLogModel).order_by(LeagueLogModel.log_created_at.desc())
            
            conditions = []
            if league_id:
                conditions.append(LeagueLogModel.league_id == league_id)
            if round_id:
                conditions.append(LeagueLogModel.round_id == round_id)
            if team_id:
                conditions.append(LeagueLogModel.team_id == team_id)
            if conditions:
                stmt = stmt.where(and_(*conditions))
            
            stmt = stmt.limit(limit)
            
            result = await session.execute(stmt)
            return result.scalars().all()
        
    async def fetch_dashboard(self, user_id: str):
        async with AsyncSession() as session:
            stmt_league_admin = select(LeagueAdministratorModel.league_administrator_id).where(
                LeagueAdministratorModel.user_id == user_id
            )
            result_admin = await session.execute(stmt_league_admin)
            league_administrator_id = result_admin.scalar_one_or_none()

            if not league_administrator_id:
                return None
            
            ACTIVE_STATUS = ["Pending", "Scheduled", "Ongoing"]

            stmt = (
                select(
                    LeagueModel.league_id,
                    LeagueModel.banner_url,
                    LeagueModel.league_title,
                    LeagueModel.status,
                    LeagueModel.league_description
                )
                .where(LeagueModel.league_administrator_id == league_administrator_id)
                .where(LeagueModel.status.in_(ACTIVE_STATUS))
                .limit(1)
            )

            result_league = await session.execute(stmt)
            league_row = result_league.first()

            if not league_row:
                return None
            
            dashboard = {
                "league_id": league_row.league_id,
                "banner_url": league_row.banner_url,
                "league_title": league_row.league_title,
                "status": league_row.status,
                "league_description": league_row.league_description,
            }

            return dashboard
        
    async def fetch_league_meta(self, user_id: str):
        try:
            async with AsyncSession() as session:
                stmt_league_admin = select(LeagueAdministratorModel.league_administrator_id).where(
                    LeagueAdministratorModel.user_id == user_id
                )
                result_admin = await session.execute(stmt_league_admin)
                league_administrator_id = result_admin.scalar_one_or_none()

                if not league_administrator_id:
                    return None
                
                ACTIVE_STATUS = ["Pending", "Scheduled", "Ongoing"]

                stmt = (
                    select(
                        LeagueModel.league_id,
                        LeagueModel.status
                    )
                    .where(LeagueModel.league_administrator_id == league_administrator_id)
                    .where(LeagueModel.status.in_(ACTIVE_STATUS))
                    .limit(1)
                )

                result_league = await session.execute(stmt)
                league_row = result_league.first()

                if not league_row:
                    return None
                
                dashboard = {
                    "league_id": league_row.league_id,
                    "status": league_row.status,
                }

                return dashboard
        except:
            return {
                "messaage": "No Active League Please navigate to league creation form to start new league"
            }
