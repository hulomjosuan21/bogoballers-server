from sqlite3 import IntegrityError
from quart import Blueprint, request
from quart_auth import login_required,current_user
from sqlalchemy import select
from src.services.cloudinary_service import CloudinaryService
from src.models.team import TeamModel
from src.services.email_verification import send_verification_email
from src.models.user import UserModel
from src.extensions import AsyncSession
from src.utils.api_response import ApiResponse, ApiException
from werkzeug.datastructures import FileStorage

team_mananger_bp = Blueprint('team-manager',__name__,url_prefix='/team-manager')

class TeamManagerHandler:
    @staticmethod
    @team_mananger_bp.post('/create')
    async def create_team_manager():
        try:
            data = await request.get_json()

            email = data.get("email")
            password_str = data.get("password_str")
            contact_number = data.get("contact_number")
            display_name = data.get("display_name")

            if not email or not password_str or not contact_number or not display_name:
                raise ApiException("Missing required fields")


            async with AsyncSession() as session:
                new_user = UserModel(
                    email=email,
                    contact_number=contact_number,
                    account_type="Team_Manager",
                    is_verified=True,
                    display_name=display_name
                )
                new_user.set_password(password_str)

                session.add(new_user)
                
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()
                    raise ApiException("Email already exists",409)

            return await ApiResponse.success(message="Register successfully",status_code=201)
        except Exception as e:
            return await ApiResponse.error(e)
    
    @staticmethod
    @team_mananger_bp.get('/auth')
    @login_required
    async def get_team_manager():
        try:
            user_id = request.args.get("user_id")

            async with AsyncSession() as session:
                if user_id:
                    user = await session.get(UserModel, user_id)
                else:
                    user = await session.get(UserModel, current_user.auth_id)

                if not user:
                    return await ApiResponse.error("No user found",status_code=400)

                return await ApiResponse.payload(user.to_json_for_team_manager())

        except Exception as e:
            return await ApiResponse.error(e)
    
    @staticmethod
    @team_mananger_bp.post('/create/team')
    @login_required
    async def create_team():
        try:
            user_id = request.args.get("user_id")

            form = await request.form
            files = await request.files
            logo_file = files.get("team_logo") or form.get("team_logo")

            required_fields = [
                "team_name",
                "team_address",
                "contact_number",
                "coach_name"
            ]
            missing_fields = [f for f in required_fields if not form.get(f)]
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

            team_name = form.get("team_name")
            async with AsyncSession() as session:
                new_team = TeamModel(
                    user_id= user_id if user_id else current_user.auth_id,
                    team_name= team_name,
                    team_address=form.get("team_address"),
                    contact_number=form.get("contact_number"),
                    team_motto=form.get("team_motto"),
                    team_logo_url=team_logo_url,
                    coach_name=form.get("coach_name"),
                    assistant_coach_name=form.get("assistant_coach_name"),
                    team_category=form.get("team_category")
                )

                session.add(new_team)
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()
                    raise ApiException("Failed to create team. Please try again.",500)
                
            return await ApiResponse.success(
                message=f"Team {team_name} successfully",
                status_code=201
            )
        except Exception as e:
            return await ApiResponse.error(e)
        
    @staticmethod
    @team_mananger_bp.delete('/delete/<team_id>')
    @login_required
    async def delete_team(team_id: str):
        try:
            user_id = current_user.auth_id

            async with AsyncSession() as session:
                team = await session.scalar(
                    select(TeamModel).where(
                        TeamModel.team_id == team_id,
                        TeamModel.user_id == user_id
                    )
                )
                if not team:
                    raise ApiException("Team not found or you don't have permission to delete it.",404)

                await session.delete(team)
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()
                    raise ApiException("Failed to delete team. Please try again.",500)

            return await ApiResponse.success(
                message="Team deleted successfully",
                status_code=200
            )
        except Exception as e:
            return await ApiResponse.error(e)
        
    @staticmethod
    @team_mananger_bp.get('/teams')
    @login_required
    async def get_teams():
        try:
            user_id = request.args.get("user_id")

            async with AsyncSession() as session:
                if user_id:
                    result = await session.execute(
                        select(TeamModel).where(TeamModel.user_id == user_id)
                    )
                else:
                    result = await session.execute(
                        select(TeamModel).where(TeamModel.user_id == current_user.auth_id)
                    )
                teams = result.scalars().all()

                if not teams:
                    return await ApiResponse.payload([])

                return await ApiResponse.payload([team.to_json_for_team_manager() for team in teams])
        except Exception as e:
            return await ApiResponse.error(e)