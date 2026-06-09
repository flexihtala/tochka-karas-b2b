from uuid import UUID

from apps.blocking_reasons.errors import BlockingReasonNotFoundError
from apps.blocking_reasons.repositories import BlockingReasonRepository
from apps.blocking_reasons.schemas.db import BlockingReasonUpdateSchema


class DeleteBlockingReasonUseCase:
    """DELETE /api/v1/blocking-reasons/{id} — admin-only, soft-delete.

    Hard-delete оставит висячие FK у исторических тикетов с блокировкой по этой причине,
    поэтому переключаем is_active=false. Список с фильтром is_active=true скроет её.
    """

    def __init__(self, blocking_reason_repository: BlockingReasonRepository):
        self.blocking_reason_repository = blocking_reason_repository

    async def __call__(self, reason_id: UUID) -> None:
        existing = await self.blocking_reason_repository.get_or_none(reason_id)
        if existing is None:
            raise BlockingReasonNotFoundError()

        updated = await self.blocking_reason_repository.update(
            BlockingReasonUpdateSchema(id=reason_id, is_active=False),
        )
        if updated is None:
            raise BlockingReasonNotFoundError()
