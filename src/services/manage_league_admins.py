from typing import List
from sqlalchemy import func, select
from src.models.user import UserModel
from src.models.league import LeagueModel
from src.models.league_admin import LeagueAdministratorModel
from src.extensions import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

class ManageLeagueAdministratorService:
    async def get_all_administrators(self) -> List[LeagueAdministratorModel]:
        async with AsyncSession() as session:
            try:
                stmt = (
                    select(LeagueAdministratorModel)
                    .join(LeagueAdministratorModel.account)
                    .where(UserModel.account_type != "League_Administrator_LGU")
                    .order_by(func.coalesce(
                        LeagueAdministratorModel.league_admin_updated_at,
                        LeagueAdministratorModel.league_admin_created_at
                    ).desc())
                )
                result = await session.execute(stmt)
                admins = result.scalars().unique().all()
                return admins
            except:
                return []

    async def get_all_leagues(self) -> List[LeagueModel]:
        async with AsyncSession() as session:
            try:
                stmt = (
                    select(LeagueModel)
                    .order_by(LeagueModel.league_created_at.desc())
                )
                result = await session.execute(stmt)
                leagues = result.scalars().unique().all()
                return leagues
            except:
                return []

    async def toggle_admin_operational(self, league_administrator_id: str) -> LeagueAdministratorModel | None:
        async with AsyncSession() as session:
            try:
                admin = await session.get(LeagueAdministratorModel, league_administrator_id)
                if not admin:
                    return None
                
                admin.is_operational = not admin.is_operational
                await session.commit()
                await session.refresh(admin)
                return admin
            except:
                await session.rollback()
                return None

    async def update_league_status(self, league_id: str, new_status: str) -> LeagueModel | None:
        async with AsyncSession() as session:
            try:
                league = await session.get(LeagueModel, league_id)
                if not league:
                    return None
                
                league.status = new_status
                await session.commit()
                await session.refresh(league)
                return league
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e
            except:
                return None