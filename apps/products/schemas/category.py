from pydantic import ConfigDict

from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class CategoryCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    name: str


class CategoryReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    name: str


class CategoryUpdateSchema(UpdateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    name: str | None = None
