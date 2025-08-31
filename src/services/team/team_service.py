from sqlalchemy import select, or_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import selectinload
from werkzeug.datastructures import FileStorage
from src.models.player import PlayerModel, PlayerTeamModel
from src.models.team import TeamModel
from src.services.cloudinary_service import CloudinaryException, CloudinaryService
from src.utils.api_response import ApiException
from src.extensions import AsyncSession
from src.utils.server_utils import validate_required_fields

class TeamService:
    async def fetch_many(self, search: str = None):
        async with AsyncSession() as session:
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
            return teams
    
    async def get_team_with_players(self, team_id: str):
        async with AsyncSession() as session:
            stmt = (
                select(TeamModel)
                .options(
                    selectinload(TeamModel.players)
                    .selectinload(PlayerTeamModel.player)
                    .selectinload(PlayerModel.user) 
                )
                .where(TeamModel.team_id == team_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

        
    async def create_one(self, user_id: str, form_data: dict, logo_file):
        try:
            required_fields = [
                "team_name",
                "team_address", 
                "contact_number",
                "coach_name"
            ]
            if not logo_file:
                required_fields.append("team_logo")

            validate_required_fields(form_data, required_fields)

            if isinstance(logo_file, FileStorage):
                team_logo_url = await CloudinaryService.upload_file(
                    file=logo_file,
                    folder="/team/logos"
                )
            elif isinstance(logo_file, str):
                team_logo_url = logo_file

            async with AsyncSession() as session:
                new_team = TeamModel(
                    user_id=user_id,
                    team_name=form_data.get("team_name"),
                    team_address=form_data.get("team_address"),
                    contact_number=form_data.get("contact_number"),
                    team_motto=form_data.get("team_motto", None),
                    team_logo_url=team_logo_url,
                    team_category=form_data.get("team_category"),
                    coach_name=form_data.get("coach_name"),
                    assistant_coach_name=form_data.get("assistant_coach_name", None),
                )

                session.add(new_team)
                await session.commit()
                
                return f"Team {form_data.get("team_name")} successfully"
        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise
        
    async def create_many(self, teams: list[dict]):
        try:
            async with AsyncSession() as session:
                new_teams = []

                for team in teams:
                    required_fields = [
                        "user_id",
                        "team_name",
                        "team_address",
                        "contact_number",
                        "coach_name",
                        "team_logo"
                    ]

                    validate_required_fields(team, required_fields)

                    new_team = TeamModel(
                        user_id=team.get("user_id"),
                        team_name=team.get("team_name"),
                        team_address=team.get("team_address"),
                        contact_number=team.get("contact_number"),
                        team_motto=team.get("team_motto", None),
                        team_logo_url=team.get("team_logo"),
                        coach_name=team.get("coach_name"),
                        team_category=team.get("team_category", None),
                        assistant_coach_name=team.get("assistant_coach_name", None),
                        is_recruiting=team.get("is_recruiting", False)
                    )
                    new_teams.append(new_team)

                session.add_all(new_teams)
                await session.commit()

                return f"{len(new_teams)} teams successfully created"
        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise

    async def delete_one(self, team_id: str):
        async with AsyncSession() as session:
            try:
                team = await self.get_team(session=session,team_id=team_id)
                team_logo_url = team.team_logo_url
                if not team:
                    raise ApiException("Team not found or you don't have permission to delete it.", 404)

                await session.delete(team)
                await session.commit()
                
                await CloudinaryService.delete_file_by_url(team_logo_url)

                return "Team deleted successfully"
            except (IntegrityError, SQLAlchemyError, CloudinaryException):
                await session.rollback()
                raise

    async def get_many(self, user_id: str):
        async with AsyncSession() as session:
            result = (
                select(TeamModel)
                .options(
                    selectinload(TeamModel.user),
                    selectinload(TeamModel.players)
                    .selectinload(PlayerTeamModel.player)
                    .selectinload(PlayerModel.user)
                )
                .where(TeamModel.user_id == user_id)
            )
            result = await session.execute(result)
            teams = result.scalars().all()

            if not teams:
                return []

            return teams 
            
    async def get_team(self, session, team_id: str):
        return await session.get(TeamModel, team_id)
        
    async def update_one(self, team_id: str, data: dict):
        try:
            async with AsyncSession() as session:
                team = await self.get_team(session=session,team_id=team_id)
                
                if not team:
                    raise ApiException("No team found.")
                    
                team.copy_with(**data)
                await session.commit()
            
            return "Team updated successfully."
        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise