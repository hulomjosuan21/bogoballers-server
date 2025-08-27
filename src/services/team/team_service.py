from sqlalchemy import select, or_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import selectinload
from werkzeug.datastructures import FileStorage
from src.models.team import TeamModel
from src.services.cloudinary_service import CloudinaryService
from src.utils.api_response import ApiException
from src.extensions import AsyncSession


class TeamService:
    async def create(self, user_id: str, form_data: dict, logo_file):
        required_fields = [
            "team_name",
            "team_address", 
            "contact_number",
            "coach_name"
        ]
        missing_fields = [f for f in required_fields if not form_data.get(f)]
        if not logo_file:
            missing_fields.append("team_logo")

        if missing_fields:
            raise ApiException(f"Missing required fields: {', '.join(missing_fields)}")

        if isinstance(logo_file, FileStorage):
            team_logo_url = await CloudinaryService.upload_file(
                file=logo_file,
                folder="/team-logos"
            )
        elif isinstance(logo_file, str):
            team_logo_url = logo_file

        team_name = form_data.get("team_name")
        
        async with AsyncSession() as session:
            try:
                new_team = TeamModel(
                    user_id=user_id,
                    team_name=team_name,
                    team_address=form_data.get("team_address"),
                    contact_number=form_data.get("contact_number"),
                    team_motto=form_data.get("team_motto"),
                    team_logo_url=team_logo_url,
                    coach_name=form_data.get("coach_name"),
                    assistant_coach_name=form_data.get("assistant_coach_name"),
                    team_category=form_data.get("team_category")
                )

                session.add(new_team)
                await session.commit()
                
                return f"Team {team_name} successfully"
            except IntegrityError:
                await session.rollback()
                raise ApiException("Failed to create team. Please try again.", 500)
            except (SQLAlchemyError):
                await session.rollback()
                raise

    async def delete(self, team_id: str, user_id: str):
        async with AsyncSession() as session:
            try:
                team = await session.scalar(
                    select(TeamModel).where(
                        TeamModel.team_id == team_id,
                        TeamModel.user_id == user_id
                    )
                )
                if not team:
                    raise ApiException("Team not found or you don't have permission to delete it.", 404)

                await session.delete(team)
                await session.commit()

                return "Team deleted successfully"
            except IntegrityError:
                await session.rollback()
                raise ApiException("Failed to delete team. Please try again.", 500)
            except (SQLAlchemyError):
                await session.rollback()
                raise

    async def get_many(self, user_id: str):
        async with AsyncSession() as session:
            result = await session.execute(
                select(TeamModel).where(TeamModel.user_id == user_id)
            )
            teams = result.scalars().all()

            if not teams:
                return []

            return [team.to_json_for_team_manager() for team in teams]

    async def fetch_many(self, search: str = None):
        async with AsyncSession() as session:
            try:
                query = select(TeamModel).options(selectinload(TeamModel.user))

                if search:
                    search_term = f"%{search}%"
                    query = query.where(
                        or_(
                            TeamModel.team_name.ilike(search_term),
                            TeamModel.team_category.ilike(search_term),
                            TeamModel.coach_name.ilike(search_term),
                            TeamModel.team_address.ilike(search_term),
                        )
                    )
                result = await session.execute(query)
                teams = result.scalars().all()
                teams_data = [t.to_json() for t in teams]

                return teams_data
            except Exception as e:
                print(f"Error in fetch_many: {e}")
                return []