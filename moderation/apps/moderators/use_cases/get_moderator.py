from uuid import UUID

from apps.auth.repositories import ModeratorRepository
from apps.moderators.errors import ModeratorNotFoundError
from apps.moderators.schemas.response import ModeratorResponseSchema


class GetModeratorUseCase:
    """Используется и для GET /moderators/{id} (admin), и для GET /moderators/me (current).

    Для /me роутер просто передаёт current_user.id.
    """

    def __init__(self, moderator_repository: ModeratorRepository):
        self.moderator_repository = moderator_repository

    async def __call__(self, moderator_id: UUID) -> ModeratorResponseSchema:
        moderator = await self.moderator_repository.get_or_none(moderator_id)
        if moderator is None:
            raise ModeratorNotFoundError()
        return ModeratorResponseSchema.model_validate(moderator)
