from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.extensions import AsyncSession
from src.models.user import UserModel
from src.utils.api_response import ApiException

class TeamManagerService:
    async def create_one(self, email: str, password_str: str, contact_number: str, display_name: str):
        if not email or not password_str or not contact_number or not display_name:
            raise ApiException("Missing required fields")
            
        async with AsyncSession() as session:
            try:
                new_user = UserModel(
                    email=email,
                    contact_number=contact_number,
                    account_type="Team_Manager",
                    is_verified=True,
                    display_name=display_name
                )
                new_user.set_password(password_str)
                
                session.add(new_user)
                await session.commit()
                
                return "Register successfully"
            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise

    async def get_authenticated_user(self, user_id: str = None, current_user_id: str = None):
        async with AsyncSession() as session:
            if user_id:
                user = await session.get(UserModel, user_id)
            else:
                user = await session.get(UserModel, current_user_id)
            
            if not user:
                raise ApiException("No user found", 400)
            
            return user.to_json_for_team_manager()