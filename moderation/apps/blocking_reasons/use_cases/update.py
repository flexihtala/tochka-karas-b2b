from uuid import UUID

from apps.blocking_reasons.errors import BlockingReasonNotFoundError
from apps.blocking_reasons.repositories import BlockingReasonRepository
from apps.blocking_reasons.schemas.db import BlockingReasonUpdateSchema
from apps.blocking_reasons.schemas.request import BlockingReasonUpdateRequestSchema
from apps.blocking_reasons.schemas.response import BlockingReasonResponseSchema


class UpdateBlockingReasonUseCase:
    """PATCH /api/v1/blocking-reasons/{id} — admin-only, частичное обновление.

    По спеке менять можно title, description, is_active. code не редактируется (стабильный
    идентификатор), hard_block не редактируется (терминальная семантика).
    """

    def __init__(self, blocking_reason_repository: BlockingReasonRepository):
        self.blocking_reason_repository = blocking_reason_repository

    async def __call__(
        self,
        reason_id: UUID,
        data: BlockingReasonUpdateRequestSchema,
    ) -> BlockingReasonResponseSchema:
        existing = await self.blocking_reason_repository.get_or_none(reason_id)
        if existing is None:
            raise BlockingReasonNotFoundError()

        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return BlockingReasonResponseSchema.model_validate(existing)

        updated = await self.blocking_reason_repository.update(
            BlockingReasonUpdateSchema(id=reason_id, **updates),
        )
        if updated is None:
            raise BlockingReasonNotFoundError()
        return BlockingReasonResponseSchema.model_validate(updated)
