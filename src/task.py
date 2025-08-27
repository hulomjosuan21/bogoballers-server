from src.models.user import UserModel
from src.extensions import send_fcm_notification
class Task:
    async def task_with_session(self, session):
        user = await session.get(UserModel, "user-cd92523e-7a3d-433d-8f71-aff44840ae21")
        user.email = "dakit-admin@email.com"
        await session.commit()
        print("Update success..")

    async def task_without_session(self):
        print("Something is working background...")
        # await send_fcm_notification(
        #     token="dEfjxKGOS76hLJ7YiDx6Sd:APA91bHC-HGqcvsEcp6-0JYcyGH2aiyNmXMHi4pdTMvq4BOye8ffn8OtPaV2lj36KKVuEugEzadfQSlpFU1JNMvB-G0IVU94VTls2YBMXX2EzuT5WMQ-ACc",
        #     title="Test",
        #     body="Test Data",
        #     data=None
        # )