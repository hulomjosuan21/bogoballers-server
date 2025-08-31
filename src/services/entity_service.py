import asyncio
from quart_auth import login_user
from sqlalchemy import select
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
class EntityService:
    async def search_team_or_player(self, query: str):

        players_task = player_service.search_players(query, limit=10)
        teams_task = team_service.search_teams(query, limit=10)
        
        players, teams = await asyncio.gather(players_task, teams_task)
        
        results = []
        
        for player in players:
            player_data = player.to_json_for_query_search()
            results.append({
                'type': 'player',
                'data': player_data,
                'relevance_score': self._calculate_player_relevance(player, query)
            })
        
        for team in teams:
            team_data = team.to_json_for_query_search()
            results.append({
                'type': 'team',
                'data': team_data,
                'relevance_score': self._calculate_team_relevance(team, query)
            })
        
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return {
            'query': query,
            'total_results': len(results),
            'players_count': len(players),
            'teams_count': len(teams),
            'results': results[:20]
        }
    
    def _calculate_player_relevance(self, player, query: str) -> float:
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
            score += 3.0
            
        return score
    
    def _calculate_team_relevance(self, team, query: str) -> float:
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
    
    async def login(self, form):
        email = form.get("email")
        password = form.get("password")

        async with AsyncSession() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.email == email)
            )
            user = result.scalar_one_or_none()

            if not user or not user.verify_password(password):
                raise ApiException("Invalid email or password")

            auth_user = AuthUser(user)
            login_user(auth_user)

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
            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise