from typing import List
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.services.league.league_service import LeagueService
from src.services.cloudinary_service import CloudinaryService
from src.extensions import AsyncSession
from src.models.league_admin import LeagueAdministratorModel
from src.models.user import UserModel
from src.utils.api_response import ApiException
from datetime import datetime, timezone
from src.extensions import settings
from sqlalchemy.orm import joinedload, selectinload

class LeagueAdministratorService:
    async def get_many(self) -> List[dict]:
        async with AsyncSession() as session:
            conditions = [
                LeagueAdministratorModel.geo_id == "bogo-2025",
                ~UserModel.account_type.in_(
                    ["Player", "League_Administrator_LGU", "Team_Manager"]
                ),
            ]

            stmt = (
                select(LeagueAdministratorModel)
                .join(LeagueAdministratorModel.account)
                .where(*conditions)
            )

            result = await session.execute(stmt)

            league_admins = []
            for league_admin in result.scalars().all():
                league = await LeagueService.get_one_active(
                    session, league_admin.league_administrator_id, {"condition": "Active"}
                )
                league_admins.append(
                    {
                        **league_admin.to_json(), 
                        "active_league": league.to_json() if league else None,
                    }
                )

            return league_admins
            
    
    async def search_league_administrators(self, session, search: str, limit: int = 10) -> List[LeagueAdministratorModel]:
        query = select(LeagueAdministratorModel)

        search_term = f"%{search}%"
        query = query.where(
            or_(
                func.lower(LeagueAdministratorModel.organization_name).like(func.lower(search_term)),
                func.lower(LeagueAdministratorModel.organization_type).like(func.lower(search_term)),
                func.lower(LeagueAdministratorModel.organization_address).like(func.lower(search_term))
            )
        )
        
        query = query.order_by(
            case(
                (func.lower(LeagueAdministratorModel.organization_name) == func.lower(search), 1),
                (func.lower(LeagueAdministratorModel.organization_name).like(func.lower(f"{search}%")), 2),
                else_=3
            ),
            LeagueAdministratorModel.organization_name
        ).limit(limit)
            
        result = await session.execute(query)
        return result.scalars().all()
    
    async def get_one(self, session, user_id: str) -> LeagueAdministratorModel | None:
        stmt = (
            select(LeagueAdministratorModel)
            .where(LeagueAdministratorModel.user_id == user_id)
        )
        result = await session.execute(stmt)
        return result.unique().scalar_one_or_none()
    
    async def update_one(self, user_id: str, data: dict):
        async with AsyncSession() as session:
            try:
                league_admin_result = (
                    select(LeagueAdministratorModel)
                    .where(LeagueAdministratorModel.user_id == user_id)
                )
                result = await session.execute(league_admin_result)
                league_admin = result.unique().scalar_one_or_none()

                if not league_admin:
                    raise ApiException("League Administrator not found", 404)
                league_admin.copy_with(**data)

                await session.commit()
                return "Update success."
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e

    async def authenticate_login(self, email: str, password: str):
        async with AsyncSession() as session:
            result = await session.execute(select(UserModel).where(UserModel.email == email))
            user = result.scalar_one_or_none()

            if not user or not user.verify_password(password):
                raise ApiException("Invalid credentials", 401)

            league_admin_id = None
            if user.account_type in ("League_Administrator_Local", "League_Administrator_LGU"):
                result = await session.execute(
                    select(LeagueAdministratorModel).where(LeagueAdministratorModel.user_id == user.user_id)
                )
                league_admin = result.scalar_one_or_none()
                if league_admin:
                    league_admin_id = league_admin.league_administrator_id

            claims = {
                "sub": str(user.user_id),
                "email": user.email,
                "account_type": user.account_type,
                "league_administrator_id": league_admin_id,
                "is_verified": user.is_verified
            }

            return user, claims

    async def get_authenticated_admin(self, user_id: str):
        async with AsyncSession() as session:
            league_admin_result = (
                select(LeagueAdministratorModel)
                .where(LeagueAdministratorModel.user_id == user_id)
            )
            result = await session.execute(league_admin_result)
            league_admin = result.unique().scalar_one_or_none()

            if not league_admin:
                raise ApiException("League Administrator not found", 404)

            if league_admin.account.account_type not in (
                "League_Administrator_Local",
                "League_Administrator_LGU",
            ):
                raise ApiException("Not a League Administrator", 403)

            return league_admin.to_json()

    async def create_one(self, email: str, password_str: str, contact_number: str, 
                    organization_type: str, organization_name: str, organization_address: str,
                    file=None, organization_logo_str: str = None):
        user = UserModel(
            email=email,
            contact_number=contact_number,
            account_type="League_Administrator_Local",
            verification_token_created_at=datetime.now(timezone.utc),
            is_verified=True
        )
        user.set_password(password_str)
        
        async with AsyncSession() as session:
            try:
                session.add(user)
                await session.flush()

                league_admin = LeagueAdministratorModel(
                    user_id=user.user_id,
                    organization_type=organization_type,
                    organization_name=organization_name,
                    organization_address=organization_address,
                    organization_logo_url=None
                )
                session.add(league_admin)
                await session.commit()

                organization_logo_url = None

                if file:
                    try:
                        organization_logo_url = await CloudinaryService.upload_file(
                            file=file,
                            folder=settings['league_admin_organization_logo_folder']
                        )
                    except Exception as e:
                        raise ApiException("⚠ Logo upload failed")

                elif organization_logo_str and organization_logo_str.strip():
                    organization_logo_url = organization_logo_str.strip()

                if organization_logo_url:
                    async with AsyncSession() as session:
                        result = await session.get(LeagueAdministratorModel, league_admin.league_administrator_id)
                        if result:
                            result.organization_logo_url = organization_logo_url
                            await session.commit()

                return "League Administrator registered successfully. Please check your email for verification."
            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise ApiException("Email already registered or league admin already exists.",409)