from typing import List
from sqlalchemy import Date, cast, select, update
from src.services.league.league_category_service import LeagueCategoryService
from src.engines.league_finalization_engine import LeagueFinalizationEngine
from src.engines.league_progression_engine import LeagueProgressionEngine
from src.engines.match_generation_engine import MatchGenerationEngine
from src.models.match import LeagueMatchModel
from src.extensions import AsyncSession
from src.models.league import LeagueCategoryRoundModel
from src.models.team import LeagueTeamModel
from datetime import date, datetime, timezone, timedelta, UTC
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.utils.api_response import ApiException

class LeagueMatchService:
    async def update_one(self, league_match_id: str, data: dict):
        try:
            async with AsyncSession() as session:
                league_match = await session.get(LeagueMatchModel, league_match_id)
                
                if not league_match:
                    raise ApiException("No found match")
                
                if "scheduled_date" in data:
                    raw_date = data.pop("scheduled_date")

                    if raw_date is not None:
                        if isinstance(raw_date, str):
                            league_match.scheduled_date = datetime.fromisoformat(
                                raw_date.replace("Z", "+00:00")
                            )
                        elif isinstance(raw_date, (int, float)):
                            league_match.scheduled_date = datetime.fromtimestamp(raw_date / 1000)
                        elif isinstance(raw_date, datetime):
                            league_match.scheduled_date = raw_date
                        else:
                            raise TypeError(f"Invalid type for scheduled_date: {type(raw_date)}")

                league_match.copy_with(**data)
                await session.commit()
                
                return "Success"
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e
        
    async def get_one(self, league_match_id: str) -> LeagueMatchModel:
        async with AsyncSession() as session:
            league_match = await session.get(LeagueMatchModel, league_match_id)
            
            if not league_match:
                raise ApiException("No found match.")
            
            return league_match
        
    async def get_many(self, league_category_id: str, round_id: str, data: dict):
        async with AsyncSession() as session:
            conditions = [LeagueMatchModel.league_category_id == league_category_id, LeagueMatchModel.round_id == round_id]
            
            if data:
                condition = data.get("condition")

                if condition == "Unscheduled":
                    conditions.extend([
                        LeagueMatchModel.status == "Unscheduled",
                        LeagueMatchModel.scheduled_date.is_(None)
                    ])

                elif condition == "Scheduled":
                    conditions.extend([
                        LeagueMatchModel.status == "Scheduled",
                        LeagueMatchModel.scheduled_date.is_not(None)
                    ])

                elif condition == "Completed":
                    conditions.append(LeagueMatchModel.status == "Completed")

                elif condition == "Upcoming":
                    now = datetime.now(timezone.utc)
                    two_days_from_now = now + timedelta(days=2)

                    conditions.extend([
                        LeagueMatchModel.status == "Scheduled",
                        LeagueMatchModel.scheduled_date <= two_days_from_now,
                        LeagueMatchModel.scheduled_date >= now
                    ])      
            
            stmt = select(LeagueMatchModel).where(*conditions)
            
            result = await session.execute(stmt)
            
            return result.scalars().all()
    

    async def generate_first_elimination_round(
        self,
        league_id: str,
        elimination_round_id: str
    ) -> str:
        try:
            async with AsyncSession() as session:
                league_round = await session.get(LeagueCategoryRoundModel, elimination_round_id)
                if not league_round:
                    raise ValueError(f"Round not found: {elimination_round_id}")

                accepted_teams = await LeagueCategoryService.get_eligible_teams(session, league_round.league_category_id)

                generator = MatchGenerationEngine(league_id, league_round, accepted_teams)
                matches = generator.generate()

                session.add_all(matches)
                await session.commit()

                return f"{len(matches)} matches generated."
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e
        
    async def progress_to_next_round(
        self,
        league_id: str,
        current_round_id: str,
        next_round_id: str
    ) -> str:
        try:
            async with AsyncSession() as session:
                current_round = await session.get(LeagueCategoryRoundModel, current_round_id)
                if not current_round:
                    raise ValueError(f"Current round not found: {current_round_id}")

                next_round = await session.get(LeagueCategoryRoundModel, next_round_id)
                if not next_round:
                    raise ValueError(f"Next round not found: {next_round_id}")

                eligible_teams = await self._get_eligible_teams(session, current_round.league_category_id)

                match_query = await session.execute(
                    select(LeagueMatchModel).where(
                        LeagueMatchModel.round_id == current_round.round_id
                    )
                )
                completed_matches = match_query.scalars().all()

                progression = LeagueProgressionEngine(
                    league_id=league_id,
                    current_round=current_round,
                    next_round=next_round,
                    matches=completed_matches,
                    teams=eligible_teams
                )
                next_matches = progression.generate_next_matches()

                session.add_all(next_matches)
                await session.commit()

                return f"{len(next_matches)} matches generated."
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e

    async def finalize_tournament_results(
        final_round_id: str
    ) -> str:
        PH_TZ = timezone(timedelta(hours=8))
        now = datetime.now(PH_TZ)

        try:
            async with AsyncSession() as session:
                final_round = await session.get(LeagueCategoryRoundModel, final_round_id)
                if not final_round:
                    raise ValueError(f"Final round not found: {final_round_id}")

                match_query = await session.execute(
                    select(LeagueMatchModel).where(
                        LeagueMatchModel.round_id == final_round.round_id
                    )
                )
                matches = match_query.scalars().all()

                engine = LeagueFinalizationEngine(final_round, matches)
                standings = engine.get_final_standings()

                if "champion" in standings:
                    await session.execute(
                        update(LeagueTeamModel)
                        .where(LeagueTeamModel.league_team_id == standings["champion"])
                        .values(final_rank=1, is_champion=True, finalized_at=now)
                    )

                if "runner_up" in standings:
                    await session.execute(
                        update(LeagueTeamModel)
                        .where(LeagueTeamModel.league_team_id == standings["runner_up"])
                        .values(final_rank=2, finalized_at=now)
                    )

                if "third_place" in standings:
                    await session.execute(
                        update(LeagueTeamModel)
                        .where(LeagueTeamModel.league_team_id == standings["third_place"])
                        .values(final_rank=3, finalized_at=now)
                    )

                await session.commit()

                return "Success nagud ang final"
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e
