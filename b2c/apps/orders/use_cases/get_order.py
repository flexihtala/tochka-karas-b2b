"""US-ORD-02: GET /api/v1/orders/{id} — детали заказа.

IDOR-prevention:
- user_id берётся из JWT.
- Запрос в репозитории фильтрует по (id, user_id) — чужой заказ невидим.
- Если не нашли — 404 ORDER_NOT_FOUND (не 403), чтобы не раскрывать существование
  чужих ресурсов (см. канон, §"Authorization (IDOR prevention)").

Ответ собирается единым ассемблером `assemble_order_response` — той же формой,
что checkout и cancel (цены из OrderItem-снапшота, НЕ из текущего B2B).

ADR — см. b2c/docs/adr/0002-list-and-detail-idor.md.
"""

from uuid import UUID

from apps.addresses.repositories import AddressRepository
from apps.orders.errors import OrderNotFoundError
from apps.orders.repositories import OrderItemRepository, OrderRepository
from apps.orders.schemas.response import OrderResponseSchema
from apps.orders.use_cases.response_assembler import assemble_order_response
from apps.payment_methods.repositories import PaymentMethodRepository
from shared.auth_lib import AuthenticatedUserSchema


class GetOrderUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        order_item_repository: OrderItemRepository,
        address_repository: AddressRepository,
        payment_method_repository: PaymentMethodRepository,
    ):
        self.order_repository = order_repository
        self.order_item_repository = order_item_repository
        self.address_repository = address_repository
        self.payment_method_repository = payment_method_repository

    async def __call__(self, order_id: UUID, current_user: AuthenticatedUserSchema) -> OrderResponseSchema:
        order = await self.order_repository.get_for_user(order_id, current_user.id)
        if order is None:
            raise OrderNotFoundError()

        return await assemble_order_response(
            order,
            order_item_repository=self.order_item_repository,
            address_repository=self.address_repository,
            payment_method_repository=self.payment_method_repository,
        )
