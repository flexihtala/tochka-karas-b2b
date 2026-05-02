import re

from pydantic import BaseModel, Field, field_validator

from apps.auth.services.inn_validator import InnValidator

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
PHONE_RE = re.compile(r'^\+[1-9]\d{7,14}$')


class RegisterSellerRequestSchema(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    company_name: str = Field(min_length=1, max_length=255)
    inn: str = Field(min_length=10, max_length=12)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)

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

    @field_validator('inn')
    @classmethod
    def validate_inn(cls, value: str) -> str:
        value = value.strip()
        if not InnValidator.is_valid(value):
            raise ValueError('invalid inn')
        return value

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not PHONE_RE.fullmatch(value):
            raise ValueError('invalid phone')
        return value


class LoginRequestSchema(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1)

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.fullmatch(value):
            raise ValueError('invalid email')
        return value


class RefreshRequestSchema(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequestSchema(BaseModel):
    refresh_token: str = Field(min_length=1)
