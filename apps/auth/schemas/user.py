from datetime import datetime

from pydantic import ConfigDict

from apps.auth.enums import UserRole
from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class UserCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    email: str
    password_hash: str
    role: UserRole
    is_active: bool = True
    password_changed_at: datetime | None = None
    company_name: str | None = None
    inn: str | None = None
    first_name: str
    last_name: str
    phone: str | None = None


class UserReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    email: str
    password_hash: str
    role: UserRole
    is_active: bool
    password_changed_at: datetime | None
    company_name: str | None
    inn: str | None
    first_name: str
    last_name: str
    phone: str | None
    created_at: datetime
    updated_at: datetime


class UserUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    email: str | None = None
    password_hash: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password_changed_at: datetime | None = None
    company_name: str | None = None
    inn: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
