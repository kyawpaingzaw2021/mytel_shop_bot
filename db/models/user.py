from datetime import datetime
from sqlalchemy import BigInteger, String, Numeric, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="user")
    tier_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    balance: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    default_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
