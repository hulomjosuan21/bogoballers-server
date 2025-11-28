

import asyncio

from src.extensions import db_session

async def scheduled_database_task():
    print("⏳ CRON: Starting scheduled database task...")
    async with db_session() as session:
        try:
            print("✅ CRON: Database check successful.")
        except Exception as e:
            print(f"❌ CRON: Error: {e}")

async def cleanup_task():
    print("🧹 INTERVAL: Starting cleanup task...")
    async with db_session() as session:
        try:
            await asyncio.sleep(1) # Simulate work
            print("✅ INTERVAL: Cleanup finished.")
        except Exception as e:
            print(f"❌ INTERVAL: Error: {e}")