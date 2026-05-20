from typing import Generic, TypeVar, cast, get_args

from pydantic import BaseModel
from sqlalchemy import delete, insert, select, update

from db.session_manager import SessionManager

ModelType = TypeVar('ModelType')
CreateSchemaType = TypeVar('CreateSchemaType', bound=BaseModel)
ReadSchemaType = TypeVar('ReadSchemaType', bound=BaseModel)
UpdateSchemaType = TypeVar('UpdateSchemaType', bound=BaseModel)


class DBCrudRepository(Generic[ModelType, CreateSchemaType, ReadSchemaType, UpdateSchemaType]):
    model_type: type[ModelType]
    create_schema_type: type[CreateSchemaType]
    read_schema_type: type[ReadSchemaType]
    update_schema_type: type[UpdateSchemaType]
    id_field_name = 'id'

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        base_repository_generic = next(
            (
                base
                for base in getattr(cls, '__orig_bases__', [])
                if issubclass(getattr(base, '__origin__', base), DBCrudRepository)
            ),
            None,
        )
        if not base_repository_generic:
            raise ValueError('Repository must inherit from DBCrudRepository with generic types')

        (
            cls.model_type,
            cls.create_schema_type,
            cls.read_schema_type,
            cls.update_schema_type,
        ) = cast(
            tuple[type[ModelType], type[CreateSchemaType], type[ReadSchemaType], type[UpdateSchemaType]],
            get_args(base_repository_generic),
        )

    async def create(self, data: CreateSchemaType) -> ReadSchemaType:
        values = data.model_dump()
        if values.get('id') is None:
            values.pop('id', None)

        query = insert(self.model_type).values(**values).returning(self.model_type)

        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one()

        return self.model_validate(model)

    async def get_or_none(self, id_) -> ReadSchemaType | None:
        query = select(self.model_type).where(self._id_field == id_)

        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one_or_none()

        return self.model_validate(model) if model else None

    async def update(self, data: UpdateSchemaType) -> ReadSchemaType | None:
        values = data.model_dump(exclude_unset=True, exclude={'id'})
        query = update(self.model_type).where(self._id_field == data.id).values(**values).returning(self.model_type)

        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one_or_none()

        return self.model_validate(model) if model else None

    async def delete(self, id_) -> bool:
        query = delete(self.model_type).where(self._id_field == id_)

        async with self.session_manager.get_session() as session:
            result = await session.execute(query)
            return bool(result.rowcount and result.rowcount > 0)

    def model_validate(self, model: ModelType) -> ReadSchemaType:
        return self.read_schema_type.model_validate(model)

    @property
    def _id_field(self):
        return getattr(self.model_type, self.id_field_name)
