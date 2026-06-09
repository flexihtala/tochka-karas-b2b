from uuid import UUID

from apps.auth.repositories import ModeratorRepository
from apps.auth.schemas.moderator import ModeratorUpdateSchema
from apps.moderators.errors import ModeratorNotFoundError
from apps.moderators.schemas.request import ModeratorUpdateRequestSchema
from apps.moderators.schemas.response import ModeratorResponseSchema


class UpdateModeratorUseCase:
    """PATCH /api/v1/moderators/{id} — admin-only.

    Только частичное обновление: first_name/last_name/role/is_active. Пароль/email через
    этот эндпоинт менять нельзя — это отдельный флоу (вне M1).
    """

    def __init__(self, moderator_repository: ModeratorRepository):
        self.moderator_repository = moderator_repository

    async def __call__(self, moderator_id: UUID, data: ModeratorUpdateRequestSchema) -> ModeratorResponseSchema:
        existing = await self.moderator_repository.get_or_none(moderator_id)
        if existing is None:
            raise ModeratorNotFoundError()

        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return ModeratorResponseSchema.model_validate(existing)

        updated = await self.moderator_repository.update(ModeratorUpdateSchema(id=moderator_id, **updates))
        if updated is None:
            raise ModeratorNotFoundError()
        return ModeratorResponseSchema.model_validate(updated)
