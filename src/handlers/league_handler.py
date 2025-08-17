from quart import Blueprint, request, send_file
from quart_auth import login_required, current_user
import json
import re
import bleach
from sqlalchemy import select, update
from src.helpers.league_admin_helpers import get_active_league, get_league_administrator
from src.extensions import AsyncSession, TEMPLATE_PATH
from src.models.league import LeagueCategoryModel, LeagueCategoryRoundModel, LeagueModel
from src.models.league_admin import LeagueAdministratorModel
from src.logging.log_entity_action import log_action
from dateutil.relativedelta import relativedelta
from src.services.cloudinary_service import CloudinaryService
from src.utils.api_response import ApiResponse
from datetime import datetime, date, timedelta
from io import BytesIO
from docxtpl import DocxTemplate
import traceback
import tempfile
from markdownify import markdownify as md
import os
import subprocess
from docxtpl import DocxTemplate
from sqlalchemy.orm.attributes import flag_modified

league_bp = Blueprint("league", __name__, url_prefix="/league")

ALLOWED_OPTION_KEYS = {
    "player_residency_certificate_required",
    "player_residency_certificate_valid_until"
}

class LeagueHandler:
    @staticmethod
    @league_bp.get("/<string:league_id>/export-pdf")
    @login_required
    async def export_league_pdf(league_id: str):
        try:
            async with AsyncSession() as session:
                result = await session.execute(
                    select(LeagueModel).where(LeagueModel.league_id == league_id)
                )
                league = result.scalar_one_or_none()
                if not league:
                    return await ApiResponse.error("League not found", status_code=404)

                context = {
                    "league_title": league.league_title,
                    "league_description": league.league_description,
                    "league_budget": league.league_budget,
                    "league_schedule_start": league.league_schedule.lower.strftime("%B %d, %Y"),
                    "league_schedule_end": league.league_schedule.upper.strftime("%B %d, %Y"),
                    "sportsmanship_rules_list": "\n".join(
                        f"{idx}. {rule}" for idx, rule in enumerate(league.sportsmanship_rules, start=1)
                    )
                }

                with tempfile.TemporaryDirectory() as tmpdir:
                    docx_path = os.path.join(tmpdir, "league.docx")
                    pdf_path = os.path.join(tmpdir, "league.pdf")

                    tpl = DocxTemplate(TEMPLATE_PATH)
                    tpl.render(context)
                    tpl.save(docx_path)

                    subprocess.run([
                        "C:\Program Files\LibreOffice\program\soffice.exe",
                        "--headless",
                        "--convert-to", "pdf",
                        "--outdir", tmpdir,
                        docx_path
                    ], check=True)

                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()

                buffer = BytesIO(pdf_bytes)
                buffer.seek(0)

                return await send_file(
                    buffer,
                    as_attachment=True,
                    attachment_filename=f"{league.league_title}.pdf",
                    mimetype="application/pdf"
                )

        except Exception as e:
            traceback.print_exc()
            return await ApiResponse.error(str(e), status_code=500)
    
    @staticmethod
    @league_bp.post("/category/<string:category_id>/round/<string:round_id>/update-position")
    @login_required
    async def update_round_position(category_id: str, round_id: str):
        data = await request.get_json()
        if not data or "position" not in data:
            return await ApiResponse.error("Missing 'position' in request body", status_code=400)

        position = data["position"]

        try:
            async with AsyncSession() as session:
                result = await session.execute(
                    select(LeagueCategoryRoundModel)
                    .where(LeagueCategoryRoundModel.category_id == category_id)
                    .where(LeagueCategoryRoundModel.round_id == round_id)
                )
                round_obj = result.scalar_one_or_none()

                if not round_obj:
                    return await ApiResponse.error("Round not found", status_code=404)

                round_obj.position = position

                await session.commit()
                await session.refresh(round_obj)

                return await ApiResponse.success(
                    message="Round position updated successfully",
                    payload={"round_id": round_obj.round_id, "position": round_obj.position}
                )

        except Exception as e:
            return await ApiResponse.error(str(e), status_code=500)
    
    @staticmethod
    @league_bp.post("/category/<string:category_id>/add-round")
    @login_required
    async def add_round(category_id: str):
        data = await request.get_json()
        if not data:
            return await ApiResponse.error("Missing request body", status_code=400)

        ROUND_ORDER_MAP = {
            "Elimination": 0,
            "Quarterfinal": 1,
            "Semifinal": 2,
            "Final": 3,
        }

        round_name = data.get("round_name")
        round_id = data.get("round_id")
        if not round_name or not round_id:
            return await ApiResponse.error("some fields is required", status_code=400)

        round_order = ROUND_ORDER_MAP.get(round_name, 0)

        try:
            async with AsyncSession() as session:
                new_round = LeagueCategoryRoundModel(
                    round_id=round_id,
                    category_id=category_id,
                    round_name=round_name,
                    round_order=round_order,
                    position=data.get("position")
                )
                session.add(new_round)
                await session.commit()
                await session.refresh(new_round)

                return await ApiResponse.success(
                    message="Round added successfully",
                    payload={"round_id": new_round.round_id}
                )

        except Exception as e:
            return await ApiResponse.error(str(e), status_code=500)
        
    @league_bp.put("/<string:league_id>/option")
    @login_required
    async def update_league_option(league_id: str):
        try:
            data = await request.get_json()
            if not data or "option" not in data:
                return await ApiResponse.error("Missing 'option' in request body", status_code=400)

            option_updates = data["option"]
            if not isinstance(option_updates, dict):
                return await ApiResponse.error("'option' must be an object", status_code=400)
       
            ALLOWED_OPTION_KEYS = {
                "player_residency_certificate_required",
                "player_residency_certificate_valid_until",
            }
            filtered_updates = {
                k: v for k, v in option_updates.items() if k in ALLOWED_OPTION_KEYS
            }

            if not filtered_updates:
                return await ApiResponse.error("No valid option fields to update", status_code=400)

            async with AsyncSession() as session:
                result = await session.execute(
                    select(LeagueModel).where(LeagueModel.league_id == league_id)
                )
                league = result.scalar_one_or_none()
                if not league:
                    return await ApiResponse.error("League not found", status_code=404)

                if not isinstance(league.option, dict):
                    import json
                    try:
                        league.option = json.loads(league.option or "{}")
                    except Exception:
                        league.option = {}

                league.option.update(filtered_updates)

                flag_modified(league, "option")

                await session.commit()

            return await ApiResponse.success("League options updated successfully")

        except Exception as e:
            return await ApiResponse.error(str(e), status_code=500)
    
    @staticmethod
    @league_bp.post('/create-new')
    @login_required
    async def create():
        form = await request.form
        files = await request.files

        required_fields = [
            "league_title", "league_budget", "league_description", "sportsmanship_rules",
            "registration_deadline", "opening_date", "league_schedule", "banner_image", "categories"
        ]

        for field in required_fields:
            value = form.get(field) or files.get(field)
            if not value:
                return await ApiResponse.error(f"{field} is required", status_code=400)

        league_title = form['league_title']
        league_budget = float(form['league_budget'])

        allowed_tags = [
            'p', 'br', 'strong', 'em', 'i', 'b', 's', 'del',
            'ul', 'ol', 'li', 'hr',
            'h1', 'h2', 'h3',
            'blockquote'
        ]
        league_description = bleach.clean(form['league_description'], tags=allowed_tags, strip=True)

        try:
            league_schedule = json.loads(form['league_schedule'])
            sportsmanship_rules = json.loads(form['sportsmanship_rules'])
            categories = json.loads(form['categories'])
        except json.JSONDecodeError:
            return await ApiResponse.error("Invalid format in submitted data", status_code=400)

        try:
            registration_deadline = datetime.fromisoformat(form['registration_deadline'].replace("Z", "+00:00"))
            opening_date = datetime.fromisoformat(form['opening_date'].replace("Z", "+00:00"))
        except ValueError:
            return await ApiResponse.error("Invalid date format for opening or registration date", status_code=400)

        banner_file = files.get("banner_image")
        banner_image_url = form.get("banner_image")
        banner_url = None

        if banner_file:
            try:
                banner_url = await CloudinaryService.upload_file(banner_file, folder="league_banners")
            except Exception as e:
                return await ApiResponse.error(f"Banner upload failed: {str(e)}", status_code=500)
        elif banner_image_url and re.match(r'^https?://', banner_image_url):
            banner_url = banner_image_url
        else:
            return await ApiResponse.error("Invalid or missing banner image", status_code=400)

        async with AsyncSession() as session:
            league_admin = await get_league_administrator()
            if not league_admin:
                return await ApiResponse.error("League administrator not found", status_code=404)

            league_schedule = tuple(date.fromisoformat(d[:10]) for d in league_schedule)
            new_league = LeagueModel(
                league_administrator_id=league_admin.league_administrator_id,
                league_title=league_title,
                league_budget=league_budget,
                league_description=league_description,
                registration_deadline=registration_deadline,
                opening_date=opening_date,
                league_schedule=league_schedule,
                banner_url=banner_url,
                sportsmanship_rules=sportsmanship_rules,
                league_courts=[],
                league_officials=[],
                league_referees=[],
                league_affiliates=[],
                option={
                    "player_residency_certificate_valid_until": (datetime.today() - relativedelta(months=2)).strftime("%Y-%m-%d"),
                    "player_residency_certificate_required": False
                }
            )

            new_league.categories = [
                LeagueCategoryModel(
                    category_name=cat['category_name'],
                    max_team=cat.get('max_team', 4),
                    accept_teams=cat.get('accept_teams', True),
                    team_entrance_fee_amount=cat.get('team_entrance_fee_amount', 0.0),
                    individual_player_entrance_fee_amount=cat.get('individual_player_entrance_fee_amount', 0.0),
                ) for cat in categories
            ]

            session.add(new_league)
            await session.commit()

        return await ApiResponse.success(message="League created successfully")

    @staticmethod
    @league_bp.get("/active")
    @login_required
    async def get_active_league():
        try:
            league_admin = await get_league_administrator()
            if not league_admin:
                return await ApiResponse.error("League Administrator not found", status_code=404)

            active_league = await get_active_league(league_admin.league_administrator_id)

            if not active_league:
                return await ApiResponse.payload(None)

            resource_only = request.args.get("resource", "false").lower() == "true"

            if resource_only:
                return await ApiResponse.payload(active_league.to_json_resource())
            else:
                return await ApiResponse.payload(active_league.to_json())

        except Exception as e:
            return await ApiResponse.error(str(e), status_code=500)

    @staticmethod
    @league_bp.put("/<string:league_id>/update-field/<string:field_name>")
    async def update_league_field(league_id: str, field_name: str):
        IMAGE_KEYS = {
            "league_courts": None,
            "league_officials": "photo",
            "league_referees": "photo",
            "league_affiliates": "image"
        }        

        if field_name not in IMAGE_KEYS:
            return await ApiResponse.error("Invalid field name",status_code=400)

        form = await request.form
        files = await request.files

        json_data = form.get(field_name)
        if not json_data:
            return await ApiResponse.error(f"Field '{field_name}' data required",status_code=400)

        try:
            items = json.loads(json_data)
        except json.JSONDecodeError:
            return await ApiResponse.error(f"Invalid JSON for '{field_name}'",status_code=400)

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

        return await ApiResponse.success(message=f"{field_name} updated")
    
    @staticmethod
    @league_bp.post("/<string:league_id>/add-category")
    @login_required
    async def add_category(league_id: str):
        try:
            data = await request.get_json()
            if not data:
                return await ApiResponse.error("Missing request body", status_code=400)

            required_fields = ["category_name"]
            for field in required_fields:
                if not data.get(field):
                    return await ApiResponse.error(f"{field} is required", status_code=400)

            max_team = int(data.get("max_team", 4))
            accept_teams = bool(data.get("accept_teams", True))
            team_entrance_fee_amount = float(data.get("team_entrance_fee_amount", 0.0))
            individual_player_entrance_fee_amount = float(data.get("individual_player_entrance_fee_amount", 0.0))

            async with AsyncSession() as session:
                new_category = LeagueCategoryModel(
                    league_id=league_id,
                    category_name=data["category_name"],
                    max_team=max_team,
                    accept_teams=accept_teams,
                    team_entrance_fee_amount=team_entrance_fee_amount,
                    individual_player_entrance_fee_amount=individual_player_entrance_fee_amount
                )

                session.add(new_category)
                await session.commit()

            return await ApiResponse.success(message="Category added successfully")

        except Exception as e:
            return await ApiResponse.error(str(e), status_code=500)