from src.models.user import UserModel

class Task:
    async def task_with_session(self, session):
        user = await session.get(UserModel, "user-cd92523e-7a3d-433d-8f71-aff44840ae21")
        user.email = "dakit-admin@email.com"
        await session.commit()
        print("Update success..")

    async def task_without_session(self):
        print("Something is working...")