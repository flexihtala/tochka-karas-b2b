from apps.auth.repositories import ModeratorRepository
from apps.moderators.schemas.response import ModeratorListResponseSchema, ModeratorResponseSchema


class ListModeratorsUseCase:
    """GET /api/v1/moderators — admin-only. Поддерживает фильтр ?is_active=true|false."""

    def __init__(self, moderator_repository: ModeratorRepository):
        self.moderator_repository = moderator_repository

    async def __call__(
        self,
        *,
        limit: int,
        offset: int,
        is_active: bool | None = None,
    ) -> ModeratorListResponseSchema:
        items, total_count = await self.moderator_repository.list_(limit=limit, offset=offset, is_active=is_active)
        return ModeratorListResponseSchema(
            items=[ModeratorResponseSchema.model_validate(m) for m in items],
            total_count=total_count,
            limit=limit,
            offset=offset,
        )
