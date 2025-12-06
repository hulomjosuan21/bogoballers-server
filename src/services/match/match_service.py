import asyncio
from typing import List, Optional
from sqlalchemy import  and_, func, or_, select, update
from src.models.records import LeagueMatchRecordModel
from src.services.scheduler.job_wrapper import monitor_match_status_wrapper
from src.models.player import LeaguePlayerModel, PlayerModel, PlayerTeamModel
from src.services.league.league_category_service import LeagueCategoryService
from src.models.match import LeagueMatchModel
from src.extensions import AsyncSession
from src.models.league import LeagueCategoryModel, LeagueCategoryRoundModel, LeagueModel
from src.models.team import LeagueTeamModel, TeamModel
from datetime import date, datetime, timezone, timedelta, UTC
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import aliased, selectinload
from src.utils.api_response import ApiException

class LeagueMatchService:
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
    
    async def update_one(self, league_match_id: str, data: dict):
        try:
            async with AsyncSession() as session:
                # 1. Fetch the match
                league_match = await session.get(LeagueMatchModel, league_match_id)
                
                if not league_match:
                    raise ApiException("No found match")
                
                raw_date = data.pop("scheduled_date", None)
                if raw_date is None:
                    raw_date = data.pop("scheduledDate", None)

                if raw_date is not None:
                    if raw_date == "" or raw_date is None:
                        league_match.scheduled_date = None
                    
                    elif isinstance(raw_date, str):
                        try:
                            parsed_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                            
                            if parsed_date.tzinfo is None:
                                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                                
                            league_match.scheduled_date = parsed_date
                        except ValueError:
                            raise ApiException(f"Invalid date format received: {raw_date}")

                    elif isinstance(raw_date, (int, float)):
                        league_match.scheduled_date = datetime.fromtimestamp(raw_date / 1000, tz=timezone.utc)

                if data:
                    league_match.copy_with(**data)

                await session.commit()
                
                asyncio.create_task(monitor_match_status_wrapper(league_match_id))
                
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
        
    async def fetch_unscheduled(self, league_category_id: str, round_id: str):
        async with AsyncSession() as session:
            HomeLT = aliased(LeagueTeamModel)
            HomeT = aliased(TeamModel)
            AwayLT = aliased(LeagueTeamModel)
            AwayT = aliased(TeamModel)
            stmt = (
                select(
                    LeagueMatchModel.league_match_id,
                    LeagueMatchModel.display_name,
                    LeagueMatchModel.court,
                    LeagueMatchModel.referees,
                    LeagueMatchModel.scheduled_date,
                    LeagueMatchModel.quarters,
                    LeagueMatchModel.minutes_per_quarter,
                    LeagueMatchModel.minutes_per_overtime,
                    LeagueMatchModel.home_team_score,
                    LeagueMatchModel.away_team_score,

                    HomeT.team_name.label("home_team_name"),
                    HomeT.team_logo_url.label("home_team_logo"),
                    AwayT.team_name.label("away_team_name"),
                    AwayT.team_logo_url.label("away_team_logo"),
                )
                .select_from(LeagueMatchModel)
                .outerjoin(HomeLT, LeagueMatchModel.home_team_id == HomeLT.league_team_id)
                .outerjoin(HomeT, HomeLT.team_id == HomeT.team_id)
                .outerjoin(AwayLT, LeagueMatchModel.away_team_id == AwayLT.league_team_id)
                .outerjoin(AwayT, AwayLT.team_id == AwayT.team_id)
                .where(
                    LeagueMatchModel.league_category_id == league_category_id,
                    LeagueMatchModel.status == "Unscheduled",
                    LeagueMatchModel.scheduled_date.is_(None),
                    LeagueMatchModel.round_id == round_id
                )
                .order_by(LeagueMatchModel.display_name.asc())
            )

            result = await session.execute(stmt)
            rows = result.mappings().all()
            data = []
            for row in rows:
                match_dict = {
                    "league_match_id": row.league_match_id,
                    "display_name": row.display_name,
                    "court": row.court,
                    "referees": row.referees,
                    "scheduled_date": row.scheduled_date.isoformat() if row.scheduled_date else None,
                    "quarters": row.quarters,
                    "minutes_per_quarter": row.minutes_per_quarter,
                    "minutes_per_overtime": row.minutes_per_overtime,
                    "home_team_score": row.home_team_score,
                    "away_team_score": row.away_team_score,
                    "home_team": {
                        "team_name": row.home_team_name,
                        "team_logo_url": row.home_team_logo
                    } if row.home_team_name else None,
                    "away_team": {
                        "team_name": row.away_team_name,
                        "team_logo_url": row.away_team_logo
                    } if row.away_team_name else None,
                }
                data.append(match_dict)
            
            return data

    async def fetch_scheduled(self, league_category_id: str, round_id: str):
        async with AsyncSession() as session:
            stmt = (
                select(LeagueMatchModel)
                .where(
                    LeagueMatchModel.league_category_id == league_category_id,
                    LeagueMatchModel.status == "Scheduled",
                    LeagueMatchModel.scheduled_date.is_not(None),
                    LeagueMatchModel.round_id == round_id
                )
                .order_by(
                    LeagueMatchModel.scheduled_date.asc(), 
                    LeagueMatchModel.display_name.asc()
                )
            )
            result = await session.execute(stmt)
            return result.scalars().all()
        
    async def fetch_completed(self, league_category_id: str, round_id: str):
        async with AsyncSession() as session:
            stmt = (
                select(LeagueMatchModel)
                .where(
                    LeagueMatchModel.league_category_id == league_category_id,
                    LeagueMatchModel.status == "Completed",
                    LeagueMatchModel.round_id == round_id
                )
                .order_by(
                    LeagueMatchModel.scheduled_date.desc(), 
                    LeagueMatchModel.display_name.asc()
                )
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def fetch_scheduled_dashboard(self, league_category_id: str, round_id: str):
        async with AsyncSession() as session:
            HomeLT = aliased(LeagueTeamModel)
            HomeT = aliased(TeamModel)
            AwayLT = aliased(LeagueTeamModel)
            AwayT = aliased(TeamModel)
            
            stmt = (
                select(
                    LeagueMatchModel.display_name.label("detail"),
                    LeagueMatchModel.scheduled_date,
                    HomeT.team_name.label("home_team_name"),
                    HomeT.team_logo_url.label("home_team_logo"),
                    HomeLT.wins.label("home_wins"),
                    HomeLT.losses.label("home_losses"),
                    AwayT.team_name.label("away_team_name"),
                    AwayT.team_logo_url.label("away_team_logo"),
                    AwayLT.wins.label("away_wins"),
                    AwayLT.losses.label("away_losses"),
                )
                .select_from(LeagueMatchModel)
                .outerjoin(HomeLT, LeagueMatchModel.home_team_id == HomeLT.league_team_id)
                .outerjoin(HomeT, HomeLT.team_id == HomeT.team_id)
                .outerjoin(AwayLT, LeagueMatchModel.away_team_id == AwayLT.league_team_id)
                .outerjoin(AwayT, AwayLT.team_id == AwayT.team_id)
                .where(
                    LeagueMatchModel.league_category_id == league_category_id,
                    LeagueMatchModel.status == "Scheduled",
                    LeagueMatchModel.scheduled_date.is_not(None),
                    LeagueMatchModel.round_id == round_id
                )
                .order_by(
                    LeagueMatchModel.scheduled_date.asc(), 
                    LeagueMatchModel.display_name.asc()
                )
            )

            result = await session.execute(stmt)
            return [
                {
                    "home_team": {
                        "team_name": row.home_team_name or "TBD",
                        "team_logo_url": row.home_team_logo or "",
                        "wins": row.home_wins if row.home_wins is not None else 0,
                        "losses": row.home_losses if row.home_losses is not None else 0,
                    },
                    "away_team": {
                        "team_name": row.away_team_name or "TBD",
                        "team_logo_url": row.away_team_logo or "",
                        "wins": row.away_wins if row.away_wins is not None else 0,
                        "losses": row.away_losses if row.away_losses is not None else 0,
                    },
                    "detail": row.detail,
                    "schedule_date": row.scheduled_date.isoformat() if row.scheduled_date else None
                }
                for row in result.mappings()
            ]

    async def fetch_completed_dashboard(self, league_category_id: str, round_id: str):
        async with AsyncSession() as session:
            HomeLT = aliased(LeagueTeamModel)
            HomeT = aliased(TeamModel)
            AwayLT = aliased(LeagueTeamModel)
            AwayT = aliased(TeamModel)
            
            stmt = (
                select(
                    LeagueMatchModel.display_name.label("detail"),
                    LeagueMatchModel.home_team_score,
                    LeagueMatchModel.away_team_score,
                    LeagueMatchModel.scheduled_date,
                    HomeT.team_name.label("home_team_name"),
                    HomeT.team_logo_url.label("home_team_logo"),
                    HomeLT.wins.label("home_wins"),
                    HomeLT.losses.label("home_losses"),
                    AwayT.team_name.label("away_team_name"),
                    AwayT.team_logo_url.label("away_team_logo"),
                    AwayLT.wins.label("away_wins"),
                    AwayLT.losses.label("away_losses"),
                )
                .select_from(LeagueMatchModel)
                .outerjoin(HomeLT, LeagueMatchModel.home_team_id == HomeLT.league_team_id)
                .outerjoin(HomeT, HomeLT.team_id == HomeT.team_id)
                .outerjoin(AwayLT, LeagueMatchModel.away_team_id == AwayLT.league_team_id)
                .outerjoin(AwayT, AwayLT.team_id == AwayT.team_id)
                .where(
                    LeagueMatchModel.league_category_id == league_category_id,
                    LeagueMatchModel.status == "Completed",
                    LeagueMatchModel.round_id == round_id
                )
                .order_by(
                    LeagueMatchModel.scheduled_date.desc(), 
                    LeagueMatchModel.display_name.asc()
                )
            )

            result = await session.execute(stmt)
            return [
                {
                    "home_team": {
                        "team_name": row.home_team_name or "TBD",
                        "team_logo_url": row.home_team_logo or "",
                        "wins": row.home_wins if row.home_wins is not None else 0,
                        "losses": row.home_losses if row.home_losses is not None else 0,
                    },
                    "away_team": {
                        "team_name": row.away_team_name or "TBD",
                        "team_logo_url": row.away_team_logo or "",
                        "wins": row.away_wins if row.away_wins is not None else 0,
                        "losses": row.away_losses if row.away_losses is not None else 0,
                    },
                    "home_team_score": str(row.home_team_score) if row.home_team_score is not None else "0",
                    "away_team_score": str(row.away_team_score) if row.away_team_score is not None else "0",
                    "detail": row.detail
                }
                for row in result.mappings()
            ]
        
    async def get_many(self, league_category_id: str, round_id: str, data: dict):
        async with AsyncSession() as session:
            conditions = [LeagueMatchModel.league_category_id == league_category_id]
            stmt = select(LeagueMatchModel).where(*conditions)

            if data:
                condition = data.get("condition")
                limit = data.get("limit", None)

                if condition == "Unscheduled":
                    conditions.extend([
                        LeagueMatchModel.status == "Unscheduled",
                        LeagueMatchModel.scheduled_date.is_(None),
                        LeagueMatchModel.round_id == round_id
                    ])
                    stmt = select(LeagueMatchModel).where(*conditions).order_by(LeagueMatchModel.display_name.asc())
                    
                elif condition == "Scheduled":
                    conditions.extend([
                        LeagueMatchModel.status == "Scheduled",
                        LeagueMatchModel.scheduled_date.is_not(None),
                        LeagueMatchModel.home_team_id.is_not(None),
                        LeagueMatchModel.away_team_id.is_not(None),
                        LeagueMatchModel.round_id == round_id
                    ])
                    
                    stmt = (
                        select(LeagueMatchModel)
                        .where(*conditions)
                        .order_by(
                            LeagueMatchModel.scheduled_date.asc(),
                            # LeagueMatchModel.display_name.asc()
                        )
                    )

                elif condition == "Completed":
                    conditions.extend([
                        LeagueMatchModel.status == "Completed",
                        LeagueMatchModel.home_team_id.is_not(None),
                        LeagueMatchModel.away_team_id.is_not(None),
                        LeagueMatchModel.league_category_id == league_category_id,
                    ])
                    if round_id is not None:
                        conditions.append(LeagueMatchModel.round_id == round_id)
                    stmt = select(LeagueMatchModel).where(*conditions).order_by(LeagueMatchModel.league_match_updated_at.desc())
                    if limit is not None:
                        stmt = stmt.limit(limit)
                elif condition == "Upcoming":
                    conditions.extend([
                        LeagueMatchModel.status == "Scheduled",
                        LeagueMatchModel.home_team_id.is_not(None),
                        LeagueMatchModel.away_team_id.is_not(None),
                        LeagueMatchModel.round_id == round_id,
                        LeagueMatchModel.scheduled_date > func.now()
                    ])
                    stmt = select(LeagueMatchModel).where(*conditions).order_by(LeagueMatchModel.scheduled_date.asc())
                    if limit is not None:
                        stmt = stmt.limit(limit)

                elif condition == "ByRound":
                    conditions.append(LeagueMatchModel.round_id == round_id)
                    stmt = select(LeagueMatchModel).where(*conditions).order_by(LeagueMatchModel.display_name.asc())

            result = await session.execute(stmt)
            return result.scalars().all()

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

    async def finalize_match_result(
        self,
        league_match_id: str,
        data: dict,
    ) -> Optional[str]:
        try:
            async with AsyncSession() as session:
                stmt = (
                    select(LeagueMatchModel)
                    .where(LeagueMatchModel.league_match_id == league_match_id)
                    .options(
                        selectinload(LeagueMatchModel.home_team),
                        selectinload(LeagueMatchModel.away_team), 
                        selectinload(LeagueMatchModel.home_team, LeagueTeamModel.team),
                        selectinload(LeagueMatchModel.away_team, LeagueTeamModel.team),
                    )
                )
                res = await session.execute(stmt)
                match = res.scalars().first()

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
                    player_model.total_points_scored += player_data.get('total_score', 0)

                    for json_key, model_attr in self.STATS_MAP.items():
                        stat_value = player_stats.get(json_key, 0)
                        current_value = getattr(player_model, model_attr, 0)
                        setattr(player_model, model_attr, current_value + stat_value)

                home_total_score = data['home_total_score']
                away_total_score = data['away_total_score']

                match.home_team_score = home_total_score
                match.away_team_score = away_total_score

                if home_total_score > away_total_score:
                    match.winner_team_id = match.home_team_id
                    match.loser_team_id = match.away_team_id
                    winner_name = match.home_team.team.team_name
                    winner_score = home_total_score
                    loser_score = away_total_score

                elif away_total_score > home_total_score:
                    match.winner_team_id = match.away_team_id
                    match.loser_team_id = match.home_team_id
                    winner_name = match.away_team.team.team_name
                    winner_score = away_total_score
                    loser_score = home_total_score

                else:
                    raise ValueError("Draws are not allowed in this format")

                match.status = "Completed"
                match.finalized_at = datetime.utcnow()

                league_team_ids = [match.home_team_id, match.away_team_id]
                stmt = select(LeagueTeamModel).where(
                    LeagueTeamModel.league_team_id.in_(league_team_ids),
                    LeagueTeamModel.league_category_id == match.league_category_id
                )
                result = await session.execute(stmt)
                team_models = {team.league_team_id: team for team in result.scalars().all()}

                if not team_models:
                    stmt = select(LeagueTeamModel).where(
                        LeagueTeamModel.team_id.in_(league_team_ids),
                        LeagueTeamModel.league_category_id == match.league_category_id
                    )
                    result = await session.execute(stmt)
                    team_models = {team.team_id: team for team in result.scalars().all()}

                winner_team = team_models.get(match.winner_team_id) or next(
                    (t for t in team_models.values() if t.team_id == match.winner_team_id or t.league_team_id == match.winner_team_id),
                    None
                )
                loser_team = team_models.get(match.loser_team_id) or next(
                    (t for t in team_models.values() if t.team_id == match.loser_team_id or t.league_team_id == match.loser_team_id),
                    None
                )

                if winner_team:
                    winner_team.wins += 1
                    winner_team.points += winner_score

                    if winner_team.team:
                        winner_team.team.total_wins += 1
                        winner_team.team.total_points += winner_score

                if loser_team:
                    loser_team.losses += 1
                    loser_team.points += loser_score

                    if loser_team.team:
                        loser_team.team.total_losses += 1
                        loser_team.team.total_points += loser_score

                new_record = LeagueMatchRecordModel(
                    league_id=match.league_id,
                    league_match_id=match.league_match_id,
                    record_json=data
                )

                session.add(new_record)
                await session.commit()
                await session.refresh(match)

                return f"{match.home_team.team.team_name} vs {match.away_team.team.team_name} finalized winner: {winner_name}"

        except KeyError as e:
            raise ValueError(f"Malformed match data: missing key {e}") from e
        except Exception:
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

            