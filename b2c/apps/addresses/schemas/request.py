from pydantic import BaseModel, Field


class AddressCreateRequestSchema(BaseModel):
    country: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=200)
    street: str = Field(min_length=1, max_length=200)
    postal_code: str = Field(min_length=1, max_length=20)
    comment: str | None = Field(default=None, max_length=500)
    is_default: bool = False


class AddressUpdateRequestSchema(BaseModel):
    country: str | None = Field(default=None, min_length=1, max_length=100)
    city: str | None = Field(default=None, min_length=1, max_length=200)
    street: str | None = Field(default=None, min_length=1, max_length=200)
    postal_code: str | None = Field(default=None, min_length=1, max_length=20)
    comment: str | None = Field(default=None, max_length=500)
    is_default: bool | None = None
