from quart_auth import AuthUser as BaseAuthUser
from src.models.user import UserModel

class AuthUser(BaseAuthUser):
    def __init__(self, user: UserModel):
        super().__init__(user.user_id)
        self.user = user
        self.user_id = user.user_id
        self.account_type = user.account_type
        self.email = user.email
        self.is_verified = user.is_verified
        self.fcm_token = user.fcm_token

    @property
    def auth_data(self):
        return {
            "user_id": self.user_id,
            "account_type": self.account_type,
            "email": self.email,
        }
