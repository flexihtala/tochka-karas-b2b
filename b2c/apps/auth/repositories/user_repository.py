from sqlalchemy import select

from apps.auth.models import User
from apps.auth.schemas.user import UserCreateSchema, UserReadSchema, UserUpdateSchema
from shared.db import DBCrudRepository


class UserRepository(DBCrudRepository[User, UserCreateSchema, UserReadSchema, UserUpdateSchema]):
    async def get_by_email(self, email: str) -> UserReadSchema | None:
        query = select(User).where(User.email == email)

        async with self.session_manager.get_session() as session:
            model = (await session.execute(query)).scalar_one_or_none()

        return self.model_validate(model) if model else None
