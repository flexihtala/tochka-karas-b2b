import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.auth_lib import UserRole
from shared.db import Base, IDMixin, TimestampMixin


class User(IDMixin, TimestampMixin, Base):
    """Buyer (покупатель) — единая таблица users в b2c.

    Поля минимальны для роли BUYER: имя, фамилия, телефон.
    company_name/inn не нужны (в отличие от SELLER в b2b).
    """

    __tablename__ = 'users'

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default='true')
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        email: str,
        password_hash: str,
        role: UserRole,
        first_name: str,
        last_name: str | None = None,
        phone: str | None = None,
        is_active: bool = True,
        password_changed_at: datetime | None = None,
    ):
        if id is not None:
            self.id = id
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.first_name = first_name
        self.last_name = last_name
        self.phone = phone
        self.is_active = is_active
        self.password_changed_at = password_changed_at
