from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from src.models.user import UserModel
from src.extensions import workder, AsyncSession

def my_scheduled_task():
    print("📌 Running scheduled task...")

async def test_updated():
    try:
        async with AsyncSession() as session:
            async with session.begin():
                user = await session.get(UserModel, "user-cd92523e-7a3d-433d-8f71-aff44840ae21")
                if user:
                    user.email = "dakit-admin1@email.com"
                    print("✅ Update Success (will commit on exit).")
                else:
                    print("⚠️ User not found.")
    except Exception as e:
        print("❌ Scheduled task failed:", e)

def init_worker():

    workder.add_job(
        test_updated,
        CronTrigger(hour=11, minute=47)
    )

    workder.start()
