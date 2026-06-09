import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.auth_lib import UserRole
from shared.db import Base, IDMixin, TimestampMixin


class Moderator(IDMixin, TimestampMixin, Base):
    """Модератор/админ сервиса Moderation.

    role хранится в той же таблице: MODERATOR или ADMIN. Это сделано осознанно — все
    операции по входу/JWT одинаковы, отличия только в правах на эндпоинтах
    (require_role(UserRole.ADMIN) для admin-only операций).
    """

    __tablename__ = 'moderators'

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default='true')
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        email: str,
        password_hash: str,
        role: UserRole,
        first_name: str,
        last_name: str | None = None,
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
        self.is_active = is_active
        self.password_changed_at = password_changed_at
