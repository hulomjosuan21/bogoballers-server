from __future__ import annotations
from typing import TYPE_CHECKING, List

from src.utils.mixins import UpdatableMixin

if TYPE_CHECKING:
    from src.models.user import UserModel
from datetime import datetime
from sqlalchemy import ForeignKey, String, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from argon2.exceptions import HashingError
import inspect
from src.extensions import Base, ph
from src.utils.db_utils import CreatedAt, PublicIDGenerator, UpdatedAt, UUIDGenerator
from sqlalchemy.dialects.postgresql import JSONB

class LeagueAdministratorModel(Base, UpdatableMixin):
    __tablename__ = "league_administrator_table"

    league_administrator_id: Mapped[str] = UUIDGenerator("league_administrator")
    public_league_administrator_id: Mapped[str] = PublicIDGenerator('la')
    geo_id: Mapped[str] = mapped_column(String(250), default="bogo-2025", nullable=False)

    organization_name: Mapped[str] = mapped_column(String(250), nullable=False)
    organization_logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    is_allowed: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=False,
        server_default=text("false")
    )

    is_operational: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=False,
    )
    
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users_table.user_id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    organization_type: Mapped[str] = mapped_column(String, nullable=False)
    organization_address: Mapped[str] = mapped_column(String(250), nullable=False)

    organization_country: Mapped[str] = mapped_column(String(250), nullable=False)
    organization_province: Mapped[str] = mapped_column(String(250), nullable=False)
    organization_municipality: Mapped[str] = mapped_column(String(250), nullable=False)

    organization_photo_url: Mapped[str | None] = mapped_column(String, nullable=True)

    league_admin_created_at: Mapped[datetime] = CreatedAt()
    league_admin_updated_at: Mapped[datetime] = UpdatedAt()
    
    account: Mapped["UserModel"] = relationship(
        "UserModel",
        back_populates="league_administrator",
        lazy="joined"
    )

    def to_json(self) -> dict:
        return {
            'league_administrator_id': self.league_administrator_id,
            'public_league_administrator_id': self.public_league_administrator_id,
            'user_id': self.user_id,
            'organization_name': self.organization_name,
            'organization_type': self.organization_type,
            'organization_address': self.organization_address,
            'organization_country': self.organization_country,
            'organization_province': self.organization_province,
            'organization_municipality': self.organization_municipality,
            'organization_logo_url': self.organization_logo_url,
            'league_admin_created_at': self.league_admin_created_at.isoformat(),
            'league_admin_updated_at': self.league_admin_updated_at.isoformat(),
            'is_operational': self.is_operational,
            'account': self.account.to_json(),
        }

class LeagueStaffModel(Base, UpdatableMixin):
    __tablename__ = "league_staff_table"

    staff_id: Mapped[str] = UUIDGenerator("staff")
    full_name: Mapped[str] = mapped_column(String(250), nullable=False)
    contact_info: Mapped[str] = mapped_column(String(250), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    pin_hash: Mapped[str] = mapped_column(String, nullable=False)
    
    role_label: Mapped[str] = mapped_column(String(100), nullable=False) 
    
    assigned_permissions: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)

    league_administrator_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_administrator_table.league_administrator_id", ondelete="CASCADE"),
        nullable=False
    )

    is_super: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=False,
    )

    staff_created_at: Mapped[datetime] = CreatedAt()
    staff_updated_at: Mapped[datetime] = UpdatedAt()

    league_administrator_id: Mapped[str] = mapped_column(String, ForeignKey("league_administrator_table.league_administrator_id", ondelete="CASCADE"), nullable=False)

    def set_pin(self, pin_str: str) -> None:
        if len(pin_str) < 4 or len(pin_str) > 6:
            raise ValueError("PIN must be between 4 and 6 digits")
            
        try:
            self.pin_hash = ph.hash(pin_str)
        except HashingError as e:
            raise ValueError(f"PIN hashing failed: {str(e)}")

    def verify_pin(self, pin_str: str) -> bool:
        try:
            return ph.verify(self.pin_hash, pin_str)
        except Exception:
            return False

    def to_json(self) -> dict:
        return {
            "staff_id": self.staff_id,
            "username": self.username,
            "full_name": self.full_name,
            "contact_info": self.contact_info,
            "role_label": self.role_label,
            "permissions": self.assigned_permissions,
            "league_administrator_id": self.league_administrator_id,
            "staff_created_at": self.staff_created_at,
        }

_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]