import json
import os
import subprocess
import tempfile
from datetime import datetime
from io import BytesIO
import re
from dateutil.relativedelta import relativedelta
from docxtpl import DocxTemplate
from sqlalchemy import select, update
from src.helpers.league_admin_helpers import get_active_league, get_league_administrator
from src.models.league import LeagueModel, LeagueCategoryModel
from src.services.cloudinary_service import CloudinaryService
from src.extensions import AsyncSession
from src.utils.api_response import ApiException
from src.extensions import TEMPLATE_PATH
from sqlalchemy.orm.attributes import flag_modified

ALLOWED_OPTION_KEYS = {
    "player_residency_certificate_required",
    "player_residency_certificate_valid_until"
}


class LeagueService:
    async def export_league_pdf(self, league_id: str):
        async with AsyncSession() as session:
            result = await session.execute(
                select(LeagueModel).where(LeagueModel.league_id == league_id)
            )
            league = result.scalar_one_or_none()
            if not league:
                raise ApiException("League not found")

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

            return buffer, league.league_title

    async def update_league_option(self, league_id: str, option_updates: dict):
        if not isinstance(option_updates, dict):
            raise ApiException("'option' must be an object")

        filtered_updates = {
            k: v for k, v in option_updates.items() if k in ALLOWED_OPTION_KEYS
        }

        if not filtered_updates:
            raise ApiException("No valid option fields to update")

        async with AsyncSession() as session:
            result = await session.execute(
                select(LeagueModel).where(LeagueModel.league_id == league_id)
            )
            league = result.scalar_one_or_none()
            if not league:
                raise ApiException("League not found")

            if not isinstance(league.option, dict):
                try:
                    league.option = json.loads(league.option or "{}")
                except Exception:
                    league.option = {}

            league.option.update(filtered_updates)
            flag_modified(league, "option")
            await session.commit()

            return "League options updated successfully"

    async def create_new_league(self, form_data: dict, files: dict):
        required_fields = [
            "league_title", "league_budget", "league_description", "league_address", "sportsmanship_rules",
            "registration_deadline", "opening_date", "league_schedule", "banner_image", "categories"
        ]
        for field in required_fields:
                if not (form_data.get(field) or files.get(field)):
                    raise ApiException(f"{field} is required")

        league_title = form_data['league_title']
        league_budget = float(form_data['league_budget'])
        league_description = form_data['league_description']
        league_address = form_data['league_address']

        try:
            league_schedule = json.loads(form_data['league_schedule'])
            sportsmanship_rules = json.loads(form_data['sportsmanship_rules'])
            categories = json.loads(form_data['categories'])
        except json.JSONDecodeError:
            raise ApiException("Invalid format in submitted data")

        try:
            registration_deadline = datetime.fromisoformat(form_data['registration_deadline'].replace("Z", "+00:00"))
            opening_date = datetime.fromisoformat(form_data['opening_date'].replace("Z", "+00:00"))
        except ValueError:
            raise ApiException("Invalid date format for opening or registration date")

        banner_file = files.get("banner_image")
        banner_image_url = form_data.get("banner_image")
        if banner_file:
            banner_url = await CloudinaryService.upload_file(banner_file, folder="league_banners")
        elif banner_image_url and re.match(r'^https?://', banner_image_url):
            banner_url = banner_image_url
        else:
            raise ApiException("Invalid or missing banner image")

        async with AsyncSession() as session:
            league_admin = await get_league_administrator()
            if not league_admin:
                raise ApiException("League administrator not found", 404)

            league_schedule = tuple(datetime.fromisoformat(d[:10]).date() for d in league_schedule)

            new_league = LeagueModel(
                league_administrator_id=league_admin.league_administrator_id,
                league_title=league_title,
                league_budget=league_budget,
                league_description=league_description,
                league_address=league_address,
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
                },
                categories=[
                    LeagueCategoryModel(
                        category_id=cat_id,
                    ) for cat_id in categories
                ]
            )

            session.add(new_league)
            await session.commit()

            return "League created successfully"

    async def get_active(self, resource_only: bool = False):
        league_admin = await get_league_administrator()
        if not league_admin:
            raise ApiException("League Administrator not found", 404)

        active_league = await get_active_league(league_admin.league_administrator_id)

        if not active_league:
            return None

        if resource_only:
            return active_league.to_json_resource()
        else:
            return active_league.to_json()

    async def update_league(self, league_id: str, field_name: str, json_data: str, files: dict):
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