import asyncio, heapq
from quart_auth import login_user
from sqlalchemy import select
from src.services.league.league_service import LeagueService
from src.services.league_admin_service import LeagueAdministratorService
from src.services.player.player_service import PlayerService
from src.services.team.team_service import TeamService
from src.config import Config
from src.models.player import PlayerModel
from src.models.user import UserModel
from src.extensions import AsyncSession
from src.auth.auth_user import AuthUser
from src.utils.api_response import ApiException
from datetime import datetime, timedelta, timezone
import jwt
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

player_service = PlayerService()
team_service = TeamService()
league_admin_service = LeagueAdministratorService()
league_service = LeagueService()

class CalculateEntityRelevance:
    def player_relevance(self, player, query: str) -> float:
        query_lower = query.lower()
        score = 0.0
        
        if player.full_name.lower() == query_lower:
            score += 10.0
        elif query_lower in player.full_name.lower():
            score += 5.0
            
        if player.jersey_name and query_lower in player.jersey_name.lower():
            score += 4.0
            
        if player.jersey_number and (str(int(player.jersey_number)) == query or str(player.jersey_number) == query):
            score += 8.0
            
        if player.position and any(query_lower in pos.lower() for pos in player.position):
            stats = [
                player.total_games_played or 0,
                player.total_points_scored or 0,
                player.total_assists or 0,
                player.total_rebounds or 0,
                player.total_join_league or 0
            ]
            highest_stat = max(stats)
            
            if highest_stat > 0:
                import math
                performance_bonus = math.log10(highest_stat + 1) * 3
                score += performance_bonus
            
            score += 3.0
            
        return score
    
    def team_relevance(self, team, query: str) -> float:
        query_lower = query.lower()
        score = 0.0
        
        if team.team_name.lower() == query_lower:
            score += 10.0
        elif query_lower in team.team_name.lower():
            score += 5.0
            
        if team.team_category and query_lower in team.team_category.lower():
            score += 3.0
            
        if team.coach_name and query_lower in team.coach_name.lower():
            score += 4.0
            
        if team.team_address and query_lower in team.team_address.lower():
            score += 2.0
            
        return score
    
    def admin_relevance(self, admin, query: str) -> float:
        query_lower = query.lower()
        score = 0.0
        
        if admin.organization_name.lower() == query_lower:
            score += 10.0
        elif query_lower in admin.organization_name.lower():
            score += 5.0
            
        if admin.organization_type and query_lower in admin.organization_type.lower():
            score += 4.0
            
        if admin.organization_address and query_lower in admin.organization_address.lower():
            score += 2.0
            
        return score

    def league_relevance(self, league, query: str) -> float:
        query_lower = query.lower()
        score = 0.0
        
        if league.league_title.lower() == query_lower:
            score += 10.0
        elif query_lower in league.league_title.lower():
            score += 5.0
            
        if league.status and league.status.lower() == query_lower:
            score += 8.0
        elif league.status and query_lower in league.status.lower():
            score += 4.0
            
        if league.league_address and query_lower in league.league_address.lower():
            score += 3.0
            
        from datetime import datetime
        current_year = datetime.now().year
        if league.season_year == current_year:
            score += 2.0
        elif abs(league.season_year - current_year) <= 1:
            score += 1.0
            
        return score

class EntityService():
    async def search_entity(self, query: str):
        async with AsyncSession() as session:
            tasks = [
                player_service.search_players(session, query, limit=10),
                team_service.search_teams(session, query, limit=10),
                league_admin_service.search_league_administrators(session, query, limit=10),
                league_service.search_leagues(session, query, limit=10),
            ]
            players, teams, league_admins, leagues = await asyncio.gather(*tasks, return_exceptions=True)
            
            calculate = CalculateEntityRelevance()

            results = [
                {'type': 'player', 'data': p.to_json_for_query_search(),
                 'relevance_score': calculate.player_relevance(p, query)}
                for p in players
            ] + [
                {'type': 'team', 'data': t.to_json_for_query_search(),
                 'relevance_score': calculate.team_relevance(t, query)}
                for t in teams
            ] + [
                {'type': 'league_administrator', 'data': a.to_json_for_query_search(),
                 'relevance_score': calculate.admin_relevance(a, query)}
                for a in league_admins
            ] + [
                {'type': 'league', 'data': l.to_json_for_query_search(),
                 'relevance_score': calculate.league_relevance(l, query)}
                for l in leagues
            ]

            top_results = heapq.nlargest(20, results, key=lambda x: x['relevance_score'])

            return {
                'query': query,
                'total_results': len(results),
                'players_count': len(players),
                'teams_count': len(teams),
                'leagues_count': len(leagues),
                'league_administrators_count': len(league_admins),
                'results': top_results
            }
    
    async def login(self, form):
        email = form.get("email")
        password = form.get("password")
        fcm_token = form.get("fcm_token")

        async with AsyncSession() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.email == email)
            )
            user = result.scalar_one_or_none()

            if not user or not user.verify_password(password):
                raise ApiException("Invalid email or password")

            auth_user = AuthUser(user)
            login_user(auth_user)
            
            if fcm_token and user.fcm_token != fcm_token:
                user.fcm_token = fcm_token
                await session.commit()

            entity_id = user.user_id
            if user.account_type == "Player":
                player_result = await session.execute(
                    select(PlayerModel).where(PlayerModel.user_id == user.user_id)
                )
                player = player_result.scalar_one_or_none()
                if not player:
                    raise ApiException("Player record not found for this user", 404)
                entity_id = player.player_id
            elif user.account_type != "Team_Manager":
                raise ApiException("Unauthorized account type")

            now = datetime.now(timezone.utc)
            exp = now + timedelta(weeks=1)

            payload = {
                "sub": str(user.user_id),
                "entity_id": str(entity_id),
                "account_type": user.account_type,
                "iat": int(now.timestamp()),
                "exp": int(exp.timestamp())
            }

            access_token = jwt.encode(payload, Config.SECRET_KEY, algorithm=Config.ALGORITHM)
            return {"user": user, "access_token": access_token}

    async def get_current_user(self, user_id=None, current_user=None):
        async with AsyncSession() as session:
            if user_id:
                user = await session.get(UserModel, user_id)
            else:
                user = await session.get(UserModel, current_user.auth_id)

            if not user:
                raise ApiException("No user found", 404)
            return user

    async def update_fcm(self, fcm_token, current_user):
        async with AsyncSession() as session:
            try:
                user = await session.get(UserModel, current_user.auth_id)
                if not user:
                    raise ApiException("User not found", 404)

                if user.fcm_token != fcm_token:
                    user.fcm_token = fcm_token
                    session.add(user)
                    await session.commit()
                return "FCM token updated"
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e