
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.models.league import LeagueCategoryModel, LeagueModel
from src.extensions import AsyncSession
from src.models.league_admin import LeagueAdministratorModel
from quart_auth import current_user
import traceback
async def get_league_administrator() -> LeagueAdministratorModel | None:
    async with AsyncSession() as session:
        result = await session.execute(
            select(LeagueAdministratorModel).where(
                LeagueAdministratorModel.user_id == current_user.auth_id
            )
        )
        return result.scalar_one_or_none()

async def get_active_league(league_admin_id: str) -> LeagueModel | None:
    async with AsyncSession() as session:
        try:
            result = await session.execute(
                select(LeagueModel)
                .options(selectinload(LeagueModel.categories).selectinload(LeagueCategoryModel.rounds))
                .where(
                    LeagueModel.league_administrator_id == league_admin_id,
                    LeagueModel.status.in_(["Scheduled", "Ongoing"])
                )
                .order_by(LeagueModel.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            traceback.print_exc()
            raise