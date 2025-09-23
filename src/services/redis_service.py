import redis.asyncio as redis
import json
import os
from dotenv import load_dotenv
from sqlalchemy import select
from src.models.league_admin import LeagueAdministratorModel
from src.extensions import AsyncSession
from src.models.match import LeagueMatchModel
from sqlalchemy.orm import joinedload

load_dotenv()

class RedisService:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisService, cls).__new__(cls)
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            print(f"Connecting to Redis at {redis_url}...")
            cls._instance.r = redis.from_url(redis_url, decode_responses=True)
        return cls._instance

    async def get_state(self, room_name: str):
        try:
            state_json = await self.r.get(room_name)
            if state_json:
                return json.loads(state_json)
        except Exception as e:
            print(f"Error getting state from Redis for {room_name}: {e}")
        return None

    async def set_state(self, room_name: str, state: dict):
        try:
            state_json = json.dumps(state)
            await self.r.set(room_name, state_json, ex=86400)
        except Exception as e:
            print(f"Error setting state in Redis for {room_name}: {e}")
            
    async def save_admin_live_match(self, admin_id: str, match_id: str):
        try:
            await self.r.hset("live_admins", admin_id, match_id)
        except Exception as e:
            print(f"Error saving live admin match: {e}")

    async def remove_admin_live_match(self, admin_id: str):
        try:
            await self.r.hdel("live_admins", admin_id)
        except Exception as e:
            print(f"Error removing live admin match: {e}")

    async def get_all_admin_live_matches(self) -> list[dict[str, str]]:
        try:
            async with AsyncSession() as session:
                data = await self.r.hgetall("live_admins")
                if not data:
                    return []

                match_ids = list(data.values())
                admin_ids = list(data.keys())

                # Fetch matches
                matches = (
                    await session.execute(
                        select(LeagueMatchModel)
                        .where(LeagueMatchModel.league_match_id.in_(match_ids))
                    )
                ).scalars().all()
                match_map = {m.league_match_id: m for m in matches}

                # Fetch admins
                admins = (
                    await session.execute(
                        select(LeagueAdministratorModel)
                        .where(LeagueAdministratorModel.league_administrator_id.in_(admin_ids))
                    )
                ).scalars().all()
                admin_map = {a.league_administrator_id: a for a in admins}

                result = []
                for admin_id, match_id in data.items():
                    match = match_map.get(match_id)
                    admin = admin_map.get(admin_id)
                    if not match or not admin:
                        continue
                    result.append({
                        "league_administrator_id": admin_id,
                        "league_administrator": admin.organization_name,
                        "league_match_id": match_id,
                        "home_team_name": match.home_team.team.team_name if match.home_team else None,
                        "away_team_name": match.away_team.team.team_name if match.away_team else None,
                    })
                return result
        except Exception as e:
            print(f"Error getting live admins: {e}")
            return []
