import re
from datetime import date

from pydantic import BaseModel, Field, field_validator

PHONE_RE = re.compile(r'^\+?[0-9]{10,15}$')


class BuyerUpdateRequestSchema(BaseModel):
    """Частичное обновление профиля покупателя.

    Per openapi spec: {first_name?, last_name?, phone?, date_of_birth?}.
    date_of_birth is accepted at the API edge for spec parity; persistence
    requires a model migration which is tracked separately.
    """

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = Field(default=None)

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not PHONE_RE.fullmatch(value):
            raise ValueError('invalid phone')
        return value
