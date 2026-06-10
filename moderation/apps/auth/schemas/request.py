import re

from pydantic import BaseModel, Field, field_validator

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


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
