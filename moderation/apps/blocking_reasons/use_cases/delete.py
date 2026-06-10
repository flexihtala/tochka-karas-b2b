from uuid import UUID

from apps.blocking_reasons.errors import BlockingReasonNotFoundError, BlockingReasonReferencedError
from apps.blocking_reasons.repositories import BlockingReasonRepository
from apps.blocking_reasons.schemas.db import BlockingReasonUpdateSchema
from apps.tickets.repositories import TicketRepository


class DeleteBlockingReasonUseCase:
    """DELETE /api/v1/blocking-reasons/{id} — admin-only, soft-delete.

    Hard-delete оставит висячие FK у исторических тикетов с блокировкой по этой причине,
    поэтому переключаем is_active=false. Список с дефолтным фильтром is_active=true скроет её.

    DoD US-MOD-06 (referenced_reason_cannot_be_deleted): если на причину ссылается хотя бы
    одна карточка модерации (tickets.blocking_reason_id), DELETE запрещён — 409
    BLOCKING_REASON_REFERENCED. Спрятать такую причину из справочника можно только явной
    деактивацией через PATCH {is_active: false}.
    """

    def __init__(
        self,
        blocking_reason_repository: BlockingReasonRepository,
        ticket_repository: TicketRepository,
    ):
        self.blocking_reason_repository = blocking_reason_repository
        self.ticket_repository = ticket_repository

    async def __call__(self, reason_id: UUID) -> None:
        existing = await self.blocking_reason_repository.get_or_none(reason_id)
        if existing is None:
            raise BlockingReasonNotFoundError()

        if await self.ticket_repository.exists_with_blocking_reason(reason_id):
            raise BlockingReasonReferencedError()

        updated = await self.blocking_reason_repository.update(
            BlockingReasonUpdateSchema(id=reason_id, is_active=False),
        )
        if updated is None:
            raise BlockingReasonNotFoundError()
