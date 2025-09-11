from datetime import datetime, timezone
import uuid
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

def CreatedAt() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

def UpdatedAt() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

def UUIDGenerator(prefix: str) -> Mapped[str]:
    def generate_uid() -> str:
        return f"{prefix}-{uuid.uuid4()}"
    return mapped_column(
        String,
        primary_key=True,
        default=generate_uid
    )
    
def PublicIDGenerator(prefix: str) -> Mapped[str]:
    return mapped_column(
        String(16),
        unique=True,
        default=lambda: f"{prefix}-{uuid.uuid4().hex[:6]}"
    )
