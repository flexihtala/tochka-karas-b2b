from apps.blocking_reasons.repositories import BlockingReasonRepository
from apps.blocking_reasons.schemas.response import (
    BlockingReasonListResponseSchema,
    BlockingReasonResponseSchema,
)


class ListBlockingReasonsUseCase:
    """GET /api/v1/blocking-reasons — moderator + admin доступ.

    Используется и admin-UI (для редактирования), и модераторами при выборе
    причины блокировки. Спека позволяет фильтры по hard_block и is_active.
    """

    def __init__(self, blocking_reason_repository: BlockingReasonRepository):
        self.blocking_reason_repository = blocking_reason_repository

    async def __call__(
        self,
        *,
        hard_block: bool | None = None,
        is_active: bool | None = None,
    ) -> BlockingReasonListResponseSchema:
        items = await self.blocking_reason_repository.list_(hard_block=hard_block, is_active=is_active)
        return BlockingReasonListResponseSchema(
            items=[BlockingReasonResponseSchema.model_validate(i) for i in items],
        )
