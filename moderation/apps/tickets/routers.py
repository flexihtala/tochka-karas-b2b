from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from apps.auth.schemas import ErrorResponseSchema
from apps.tickets.schemas import (
    BlockTicketRequestSchema,
    TicketResponseSchema,
)
from apps.tickets.use_cases import (
    ApproveTicketUseCase,
    BlockTicketUseCase,
    ReleaseTicketUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, get_current_user

router = APIRouter(prefix='/tickets')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
    409: {'model': ErrorResponseSchema},
}


@router.post(
    '/{ticket_id}/release',
    response_model=TicketResponseSchema,
    responses=error_responses,
)
@inject
async def release_ticket(
    ticket_id: UUID,
    use_case: FromDishka[ReleaseTicketUseCase],
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
) -> TicketResponseSchema:
    """Вернуть тикет в очередь (IN_REVIEW → PENDING). Только владелец тикета или ADMIN."""
    return await use_case(ticket_id, current_user.id, current_user.role)


@router.post(
    '/{ticket_id}/approve',
    response_model=TicketResponseSchema,
    responses=error_responses,
)
@inject
async def approve_ticket(
    ticket_id: UUID,
    use_case: FromDishka[ApproveTicketUseCase],
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
) -> TicketResponseSchema:
    """Одобрить тикет (IN_REVIEW → APPROVED). Outbox получит событие MODERATED для b2b."""
    return await use_case(ticket_id, current_user.id, current_user.role)


@router.post(
    '/{ticket_id}/block',
    response_model=TicketResponseSchema,
    responses=error_responses,
)
@inject
async def block_ticket(
    ticket_id: UUID,
    data: BlockTicketRequestSchema,
    use_case: FromDishka[BlockTicketUseCase],
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
) -> TicketResponseSchema:
    """Заблокировать товар. hard_block берётся из выбранной BlockingReason."""
    return await use_case(ticket_id, data, current_user.id, current_user.role)
