import re

from pydantic import BaseModel, Field, field_validator

PHONE_RE = re.compile(r'^\+?[0-9]{10,15}$')


class BuyerUpdateRequestSchema(BaseModel):
    """Частичное обновление профиля покупателя."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not PHONE_RE.fullmatch(value):
            raise ValueError('invalid phone')
        return value
