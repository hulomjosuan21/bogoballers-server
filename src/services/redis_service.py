import redis.asyncio as redis
import json
import os
from dotenv import load_dotenv

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
            print(f"State for room {room_name} has been updated in Redis.")
        except Exception as e:
            print(f"Error setting state in Redis for {room_name}: {e}")