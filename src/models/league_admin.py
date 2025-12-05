from __future__ import annotations
from typing import TYPE_CHECKING

from src.utils.mixins import UpdatableMixin

if TYPE_CHECKING:
    from src.models.user import UserModel
    
from datetime import datetime
from sqlalchemy import ForeignKey, String, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
import inspect
from src.extensions import Base
from src.utils.db_utils import CreatedAt, PublicIDGenerator, UpdatedAt, UUIDGenerator
        
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

_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]