import re

from pydantic import BaseModel, Field, field_validator

from shared.auth_lib import UserRole

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class ModeratorCreateRequestSchema(BaseModel):
    """Спека: ModeratorCreateRequest — email/password/first_name/role обязательны, last_name опционален.

    role ограничен {MODERATOR, ADMIN}.
    Минимум password — 12 символов (см. neomarket-moderation.yaml).
    """

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    role: UserRole

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.fullmatch(value):
            raise ValueError('invalid email')
        return value

    @field_validator('password')
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError('password must contain at least one letter and one digit')
        return value

    @field_validator('role')
    @classmethod
    def validate_role(cls, value: UserRole) -> UserRole:
        if value not in (UserRole.MODERATOR, UserRole.ADMIN):
            raise ValueError('role must be MODERATOR or ADMIN')
        return value


class ModeratorUpdateRequestSchema(BaseModel):
    """Спека: ModeratorUpdateRequest — все поля опциональны."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator('role')
    @classmethod
    def validate_role(cls, value: UserRole | None) -> UserRole | None:
        if value is None:
            return None
        if value not in (UserRole.MODERATOR, UserRole.ADMIN):
            raise ValueError('role must be MODERATOR or ADMIN')
        return value
