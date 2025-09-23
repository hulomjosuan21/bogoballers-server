import json
from typing import List, Optional
from sqlalchemy import  and_, func, or_, select, update
from src.models.player import LeaguePlayerModel, PlayerModel, PlayerTeamModel
from src.services.league.league_category_service import LeagueCategoryService
from src.engines.league_finalization_engine import LeagueFinalizationEngine
from src.engines.league_progression_engine import LeagueProgressionEngine
from src.engines.match_generation_engine import MatchGenerationEngine
from src.models.match import LeagueMatchModel
from src.extensions import AsyncSession
from src.models.league import LeagueCategoryModel, LeagueCategoryRoundModel, LeagueModel
from src.models.team import LeagueTeamModel, TeamModel
from datetime import date, datetime, timezone, timedelta, UTC
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import aliased, selectinload
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
            conditions = [LeagueMatchModel.league_category_id == league_category_id]
            
            if data:
                condition = data.get("condition")

                if condition == "Unscheduled":
                    conditions.extend([
                        LeagueMatchModel.status == "Unscheduled",
                        LeagueMatchModel.scheduled_date.is_(None),
                        LeagueMatchModel.round_id == round_id
                    ])

                elif condition == "Scheduled":
                    conditions.extend([
                        LeagueMatchModel.status == "Scheduled",
                        LeagueMatchModel.scheduled_date.is_not(None),
                        LeagueMatchModel.home_team_id.is_not(None),
                        LeagueMatchModel.away_team_id.is_not(None),
                        LeagueMatchModel.round_id == round_id
                    ])

                elif condition == "Completed":
                    conditions.extend([
                        LeagueMatchModel.status == "Completed",
                        LeagueMatchModel.home_team_id.is_not(None),
                        LeagueMatchModel.away_team_id.is_not(None),
                        LeagueMatchModel.round_id == round_id
                    ])

                elif condition == "Upcoming":
                    now = datetime.now(timezone.utc)
                    two_days_from_now = now + timedelta(days=2)

                    conditions.extend([
                        LeagueMatchModel.status == "Scheduled",
                        LeagueMatchModel.scheduled_date <= two_days_from_now,
                        LeagueMatchModel.scheduled_date >= now,
                        LeagueMatchModel.home_team_id.is_not(None),
                        LeagueMatchModel.away_team_id.is_not(None),
                        LeagueMatchModel.round_id == round_id
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
    ) -> str:
        try:
            async with AsyncSession() as session:
                current_round = await session.get(LeagueCategoryRoundModel, current_round_id)
                next_round_id = current_round.next_round_id
                
                if not current_round:
                    raise ValueError(f"Current round not found: {current_round_id}")
                

                next_round = await session.get(LeagueCategoryRoundModel, next_round_id)
                if not next_round:
                    raise ValueError(f"Next round not found: {next_round_id}")

                eligible_teams = await LeagueCategoryService.get_eligible_teams(
                    session, current_round.league_category_id
                )

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

                progression.finalize_progression_state()

                next_matches = progression.generate_next_matches()

                session.add_all(progression.teams)
                session.add_all(next_matches)

                await session.commit()

                return f"{len(next_matches)} matches generated and team states finalized."
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
        
    @staticmethod
    async def get_team_loss_count(session, team_id: str) -> int:
        result = await session.execute(
            select(func.count(LeagueMatchModel.round_id))
            .where(LeagueMatchModel.loser_team_id == team_id)
        )
        return result.scalar_one()
    
    @staticmethod
    async def get_previous_matches(
        session,
        bracket_side: str,
        round_number: int,
        league_category_id: str
    ) -> List[LeagueMatchModel]:
        result = await session.execute(
            select(LeagueMatchModel).where(
                LeagueMatchModel.bracket_side == bracket_side,
                LeagueMatchModel.round_number == round_number,
                LeagueMatchModel.league_category_id == league_category_id
            )
        )
        return result.scalars().all()

    @staticmethod
    async def get_match_by_id(session, match_id: str) -> Optional[LeagueMatchModel]:
        result = await session.execute(
            select(LeagueMatchModel).where(LeagueMatchModel.league_match_id == match_id)
        )
        return result.scalar_one_or_none()


    STATS_MAP = {
        "fg2m": "total_fg2_made",
        "fg2a": "total_fg2_attempts",
        "fg3m": "total_fg3_made",
        "fg3a": "total_fg3_attempts",
        "ftm": "total_ft_made",
        "fta": "total_ft_attempts",
        "reb": "total_rebounds",
        "ast": "total_assists",
        "stl": "total_steals",
        "blk": "total_blocks",
        "tov": "total_turnovers",
    }

    async def finalize_match_result(
        self,
        league_match_id: str,
        data: dict,
    ) -> Optional[LeagueMatchModel]:
        try:
            async with AsyncSession() as session:
                match = await LeagueMatchService.get_match_by_id(session, league_match_id)
                if not match:
                    raise ValueError(f"Match {league_match_id} not found")
                    
                if match.status == "Completed":
                    raise ValueError(f"Match {league_match_id} has already been finalized")

                if match.home_team_id is None or match.away_team_id is None:
                    raise ValueError("Cannot finalize match with unresolved teams")

                home_players = data['home_team']['players']
                away_players = data['away_team']['players']
                all_players_data = home_players + away_players

                player_ids_in_match = [p['player_id'] for p in all_players_data]

                if player_ids_in_match:
                    stmt = select(PlayerModel).where(PlayerModel.player_id.in_(player_ids_in_match))
                    result = await session.execute(stmt)
                    player_models_map = {p.player_id: p for p in result.scalars().all()}
                else:
                    player_models_map = {}

                for player_data in all_players_data:
                    player_id = player_data['player_id']
                    player_stats = player_data['summary']
                    player_model = player_models_map.get(player_id)

                    if not player_model:
                        continue

                    player_model.total_games_played += 1
                    player_model.total_points_scored += player_data['total_score']

                    for json_key, model_attr in self.STATS_MAP.items():
                        stat_value = player_stats[json_key]
                        current_value = getattr(player_model, model_attr)
                        setattr(player_model, model_attr, current_value + stat_value)
                
                home_total_score = data['home_total_score']
                away_total_score = data['away_total_score']
                
                match.home_team_score = home_total_score
                match.away_team_score = away_total_score

                if home_total_score > away_total_score:
                    match.winner_team_id = match.home_team_id
                    match.loser_team_id = match.away_team_id
                    winner_name = match.home_team.team.team_name
                elif away_total_score > home_total_score:
                    match.winner_team_id = match.away_team_id
                    match.loser_team_id = match.home_team_id
                    winner_name = match.away_team.team.team_name
                else:
                    raise ValueError("Draws are not allowed in this format")

                match.status = "Completed"

                stmt = select(LeagueTeamModel).where(
                    LeagueTeamModel.team_id.in_([match.home_team_id, match.away_team_id]),
                    LeagueTeamModel.league_category_id == match.league_category_id
                )
                result = await session.execute(stmt)
                team_models = {team.team_id: team for team in result.scalars().all()}

                winner_team = team_models.get(match.winner_team_id)
                loser_team = team_models.get(match.loser_team_id)

                if winner_team:
                    winner_team.wins += 1
                    winner_team.points += (
                        match.home_team_score if match.winner_team_id == match.home_team_id else match.away_team_score
                    )

                if loser_team:
                    loser_team.losses += 1
                    loser_team.points += (
                        match.home_team_score if match.loser_team_id == match.home_team_id else match.away_team_score
                    )

                await session.commit()
                await session.refresh(match)
                
                return f"{match.home_team.team.team_name} vs {match.away_team.team.team_name} finalized winner: {winner_name}"

        except KeyError as e:
            raise ValueError(f"Malformed match data: missing key {e}") from e
        except Exception as e:
            raise
        
    async def get_user_matches(self, user_id: str, data: dict):
        async with AsyncSession() as session:
            match = aliased(LeagueMatchModel)
            league_team = aliased(LeagueTeamModel)
            team = aliased(TeamModel)
            player = aliased(PlayerModel)
            player_team = aliased(PlayerTeamModel)
            league_player = aliased(LeaguePlayerModel)

            manager_query = (
                select(match)
                .join(league_team, or_(
                    league_team.league_team_id == match.home_team_id,
                    league_team.league_team_id == match.away_team_id
                ))
                .join(team, team.team_id == league_team.team_id)
                .where(team.user_id == user_id)
            )

            player_query = (
                select(match)
                .join(league_team, or_(
                    league_team.league_team_id == match.home_team_id,
                    league_team.league_team_id == match.away_team_id
                ))
                .join(league_player, league_player.league_team_id == league_team.league_team_id)
                .join(player_team, player_team.player_team_id == league_player.player_team_id)
                .join(player, player.player_id == player_team.player_id)
                .where(player.user_id == user_id)
            )

            union_subquery = manager_query.union(player_query).subquery()

            stmt = (
                select(LeagueMatchModel)
                .join(union_subquery, union_subquery.c.league_match_id == LeagueMatchModel.league_match_id)
                .options(
                    selectinload(LeagueMatchModel.league).selectinload(LeagueModel.categories).selectinload(LeagueCategoryModel.rounds),
                    
                    # Home team
                    selectinload(LeagueMatchModel.home_team)
                        .selectinload(LeagueTeamModel.team)
                        .selectinload(TeamModel.user),

                    selectinload(LeagueMatchModel.home_team)
                        .selectinload(LeagueTeamModel.league_players)
                        .selectinload(LeaguePlayerModel.player_team)
                        .selectinload(PlayerTeamModel.player)
                        .selectinload(PlayerModel.user),

                    # Away team
                    selectinload(LeagueMatchModel.away_team)
                        .selectinload(LeagueTeamModel.team)
                        .selectinload(TeamModel.user),

                    selectinload(LeagueMatchModel.away_team)
                        .selectinload(LeagueTeamModel.league_players)
                        .selectinload(LeaguePlayerModel.player_team)
                        .selectinload(PlayerTeamModel.player)
                        .selectinload(PlayerModel.user),
                )
            )
            
            now = datetime.now(timezone.utc)
            one_week_from_now = now + timedelta(weeks=1)
            
            if data:
                condition = data.get('condition')
                if condition == "Upcoming":
                    stmt = stmt.where(
                        and_(
                            LeagueMatchModel.scheduled_date.isnot(None), 
                            LeagueMatchModel.scheduled_date >= now,
                            LeagueMatchModel.scheduled_date <= one_week_from_now,
                            ~LeagueMatchModel.status.in_(["Cancelled", "Postponed", "Completed"])
                        )
                    ).order_by(LeagueMatchModel.scheduled_date.asc())

            result = await session.execute(stmt)
            matches = result.scalars().unique().all()
            return matches