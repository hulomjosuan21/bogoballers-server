from __future__ import annotations
from typing import  List, Optional
from src.utils.mixins import UpdatableMixin
from datetime import datetime
from sqlalchemy import Date, Float, ForeignKey, Integer, String, Boolean, Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column
import inspect
from sqlalchemy.dialects.postgresql import JSONB
from datetime import date
from src.extensions import Base
from src.utils.db_utils import CreatedAt, UpdatedAt, UUIDGenerator

category_allowed_gender_enum = SqlEnum(
    "Male",
    "Female",
    "Any",
    name="category_allowed_gender_enum",
    create_type=True
)

class CategoryModel(Base, UpdatableMixin):
    __tablename__ = "categories_table"
    
    category_id: Mapped[str] = UUIDGenerator("category")
    
    category_name: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    league_administrator_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("league_administrator_table.league_administrator_id", ondelete="CASCADE"),
        nullable=False
    )
    
    check_player_age: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=True,
    )
    player_min_age: Mapped[Optional[int]] = mapped_column(Integer,  nullable=True) 
    player_max_age: Mapped[Optional[int]] = mapped_column(Integer,  nullable=True)
    player_gender: Mapped[str] = mapped_column(category_allowed_gender_enum, nullable=False)
    check_address: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=True,
    )
    allowed_address: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    
    allow_guest_team: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_guest_player: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    guest_player_fee_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    team_entrance_fee_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    
    requires_valid_document: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allowed_documents: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    document_valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    category_created_at: Mapped[datetime] = CreatedAt()
    category_updated_at: Mapped[datetime] = UpdatedAt()
    
    def to_json(self) -> dict:
        return {
            'category_id': self.category_id,
            'category_name': self.category_name,
            'league_administrator_id': self.league_administrator_id,
            'check_player_age': self.check_player_age,
            'player_min_age': self.player_min_age,
            'player_max_age': self.player_max_age,
            'player_gender': self.player_gender,
            'check_address': self.check_address,
            'allowed_address': self.allowed_address,
            'allow_guest_team': self.allow_guest_team,
            'allow_guest_player': self.allow_guest_player,
            'guest_player_fee_amount': self.guest_player_fee_amount,
            'team_entrance_fee_amount': self.team_entrance_fee_amount,
            'requires_valid_document': self.requires_valid_document,
            'allowed_documents': self.allowed_documents,
            'document_valid_until': self.document_valid_until.isoformat() if self.document_valid_until else None,
            'category_created_at': self.category_created_at.isoformat(),
            'category_updated_at': self.category_updated_at.isoformat()
        }
    
_current_module = globals()
__all__ = [
    name for name, obj in _current_module.items()
    if not name.startswith("_")
    and (inspect.isclass(obj) or inspect.isfunction(obj))
]