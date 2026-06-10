from uuid import UUID

from apps.tickets.errors import TicketNotFoundError
from apps.tickets.repositories import TicketRepository
from apps.tickets.schemas.request import BlockTicketRequestSchema, DeclineProductRequestSchema
from apps.tickets.schemas.response import DeclineProductResponseSchema
from apps.tickets.use_cases.block_ticket import BlockTicketUseCase
from shared.auth_lib import UserRole


class DeclineProductUseCase:
    """POST /api/v1/products/{product_id}/decline — канонный alias мягкой блокировки (MOD-4).

    Тонкая обёртка над BlockTicketUseCase: находит активный тикет по product_id и делегирует
    блокировку. Канонное тело {blocking_reason_id (одна!), moderator_comment, field_reports}
    адаптируется к внутреннему контракту (blocking_reason_ids — список из одного элемента).

    Коды ответов (канон MOD-4, шаги 1-7):
    - тикет по product_id не найден / неизвестный товар → 404;
    - status != IN_REVIEW → 409 (HARD_BLOCKED → 403, необратимость);
    - чужой тикет → 403; неизвестная причина → 400; невалидный field_name → 400.

    ADR: причина с hard_block=true на этом пути НЕ отклоняется с 400, а маршрутизируется
    в hard-block семантику (статус HARD_BLOCKED) — ровно как /tickets/{id}/block сегодня
    (канон MOD-5: «тот же endpoint, определяется по hard_block причины блокировки»).
    """

    def __init__(self, ticket_repository: TicketRepository, block_ticket_use_case: BlockTicketUseCase):
        self.ticket_repository = ticket_repository
        self.block_ticket_use_case = block_ticket_use_case

    async def __call__(
        self,
        product_id: UUID,
        data: DeclineProductRequestSchema,
        moderator_id: UUID,
        role: UserRole,
    ) -> DeclineProductResponseSchema:
        # Лукап по product_id: активный (не ARCHIVED) тикет; статусные проверки
        # (IN_REVIEW/терминальность) выполняет BlockTicketUseCase — канонные 409/403.
        ticket = await self.ticket_repository.get_active_for_product(product_id)
        if ticket is None:
            raise TicketNotFoundError('Карточка модерации для товара не найдена')

        result = await self.block_ticket_use_case(
            ticket.id,
            BlockTicketRequestSchema(
                blocking_reason_ids=[data.blocking_reason_id],
                comment=data.moderator_comment,
                field_reports=data.field_reports,
            ),
            moderator_id,
            role,
        )
        return DeclineProductResponseSchema(product_id=result.product_id, status=result.status)
