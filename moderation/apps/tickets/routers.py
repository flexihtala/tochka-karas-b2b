from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from apps.auth.schemas import ErrorResponseSchema
from apps.tickets.schemas import (
    ApproveTicketRequestSchema,
    BlockTicketRequestSchema,
    DeclineProductRequestSchema,
    DeclineProductResponseSchema,
    TicketResponseSchema,
)
from apps.tickets.use_cases import (
    ApproveTicketUseCase,
    BlockTicketUseCase,
    DeclineProductUseCase,
    ReleaseTicketUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, get_current_user

router = APIRouter(prefix='/tickets')

# Канонный alias MOD-4/MOD-5: блокировка адресуется по product_id, а не по ticket_id.
products_router = APIRouter(prefix='/products')


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
    data: ApproveTicketRequestSchema | None = None,
) -> TicketResponseSchema:
    """Одобрить тикет (IN_REVIEW → APPROVED). Outbox получит событие MODERATED для b2b.

    По спеке принимает опциональное тело с полем comment (maxLength 2000).
    """
    comment = data.comment if data else None
    return await use_case(ticket_id, current_user.id, current_user.role, comment=comment)


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
    """Заблокировать товар. hard_block берётся из выбранных BlockingReason."""
    return await use_case(ticket_id, data, current_user.id, current_user.role)


@products_router.post(
    '/{product_id}/decline',
    response_model=DeclineProductResponseSchema,
    responses=error_responses,
)
@inject
async def decline_product(
    product_id: UUID,
    data: DeclineProductRequestSchema,
    use_case: FromDishka[DeclineProductUseCase],
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
) -> DeclineProductResponseSchema:
    """Канонный путь мягкой блокировки (MOD-4): POST /api/v1/products/{product_id}/decline.

    Тонкий alias над BlockTicketUseCase: тикет ищется по product_id (нет → 404), одна
    blocking_reason_id оборачивается в список. ADR: причина с hard_block=true здесь
    маршрутизируется в hard-block (MOD-5, статус HARD_BLOCKED), а не отклоняется с 400.
    """
    return await use_case(product_id, data, current_user.id, current_user.role)
