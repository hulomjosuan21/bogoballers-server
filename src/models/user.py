from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.models.league_admin import LeagueAdministratorModel
    from src.models.player import PlayerModel
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Text, DateTime, Enum as SqlEnum
from argon2.exceptions import HashingError
import inspect
from src.extensions import Base, ph
from src.utils.db_utils import CreatedAt, UUIDGenerator, UpdatedAt
from datetime import datetime, timezone

# ! Don't change order
account_type_enum = SqlEnum(
    "Player",
    "League_Administrator_Local",
    "League_Administrator_LGU",
    "Team_Manager",
    name="account_type_enum",
    create_type=True
)

class UserModel(Base):
    __tablename__ = "users_table"

    user_id: Mapped[str] = UUIDGenerator("user")

    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    contact_number: Mapped[str] = mapped_column(String(15), nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    account_type: Mapped[str] = mapped_column(account_type_enum, nullable=False)

    fcm_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    verification_token_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[DateTime] = CreatedAt()
    updated_at: Mapped[DateTime] = UpdatedAt()
    
    display_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=True)
        
    league_administrator: Mapped["LeagueAdministratorModel"] = relationship(
        "LeagueAdministratorModel", back_populates="user", uselist=False
    )
    player: Mapped["PlayerModel"] = relationship("PlayerModel", back_populates="user", uselist=False)
   
    def to_json_for_team_manager(self) -> dict:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "contact_number": self.contact_number,
            "is_verified": self.is_verified,
            "account_type": self.account_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "display_name": self.display_name
        }
    
    def to_json(self) -> dict:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "contact_number": self.contact_number,
            "is_verified": self.is_verified,
            "account_type": self.account_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    def set_password(self, password_str: str) -> None:
        try:
            self.password_hash = ph.hash(password_str)
        except HashingError as e:
            raise ValueError(f"Password hashing failed: {str(e)}")

    def verify_password(self, password_str: str) -> bool:
        try:
            return ph.verify(self.password_hash, password_str)
        except Exception:
            return False

_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]
