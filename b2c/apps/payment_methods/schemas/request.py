import re

from pydantic import BaseModel, Field, field_validator

LAST4_RE = re.compile(r'^[0-9]{4}$')


class PaymentMethodCreateRequestSchema(BaseModel):
    """Метаданные платёжного метода. ХРАНИМ ТОЛЬКО НЕ-ЧУВСТВИТЕЛЬНЫЕ ДАННЫЕ.

    НИКОГДА не принимаем полный PAN или CVC — только brand/last4/exp_year/exp_month.
    """

    brand: str = Field(min_length=1, max_length=32)
    last4: str = Field(min_length=4, max_length=4)
    exp_year: int = Field(ge=2024, le=2099)
    exp_month: int = Field(ge=1, le=12)
    is_default: bool = False

    @field_validator('last4')
    @classmethod
    def validate_last4(cls, value: str) -> str:
        if not LAST4_RE.fullmatch(value):
            raise ValueError('last4 must be 4 digits')
        return value


class PaymentMethodUpdateRequestSchema(BaseModel):
    is_default: bool | None = None
