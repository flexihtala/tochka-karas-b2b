"""US-ORD-01: POST /api/v1/orders — checkout.

Бизнес-правила (см. neomarket-canon/flows/b2c-orders-flows.md#b2c-9-checkout):

- **Idempotency**: UNIQUE на orders.idempotency_key. Повтор → возврат существующего
  заказа со статусом 200 (не 201). Гонку обрабатываем double-check: SELECT перед
  INSERT, IntegrityError на INSERT → повторный SELECT (см. ADR).
- Validate items (Pydantic уже отфильтровал quantity >= 1, non-empty).
- **Reserve в B2B** через ServiceClient (X-Service-Key b2c_to_b2b).
- 409 RESERVE_FAILED → проксируем failed_items наружу как 409.
- 503/timeout от B2B → 503 B2B_UNAVAILABLE.
- На success: создать Order(status=PAID) + OrderItem'ы с FIXED snapshot
  (unit_price, product_title, sku_name, product_id) — получаем из
  GET /api/v1/skus?ids=... (отдельный запрос к B2B перед reserve).
"""

from sqlalchemy.exc import IntegrityError

from apps.orders.b2b_client import B2BInventoryClient
from apps.orders.enums import OrderStatus
from apps.orders.errors import ReserveFailedError
from apps.orders.repositories import OrderItemRepository, OrderRepository
from apps.orders.schemas.db import OrderCreateSchema, OrderItemCreateSchema
from apps.orders.schemas.request import CheckoutRequestSchema
from apps.orders.schemas.response import OrderItemResponseSchema, OrderResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


class CheckoutUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        order_item_repository: OrderItemRepository,
        b2b_client: B2BInventoryClient,
    ):
        self.order_repository = order_repository
        self.order_item_repository = order_item_repository
        self.b2b_client = b2b_client

    async def __call__(
        self,
        data: CheckoutRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> tuple[OrderResponseSchema, bool]:
        """Возвращает (order_response, created_flag).

        created_flag=False означает идемпотентный повтор → router отдаст 200.
        created_flag=True — заказ создан в этом вызове → 201.
        """
        # 0. Idempotency: уже создавали?
        existing = await self.order_repository.get_by_idempotency_key(data.idempotency_key)
        if existing is not None:
            response = await self._assemble_response(existing)
            return response, False

        # 1. Снапшот SKU/product из B2B (нужен product_title, sku_name, price).
        sku_ids = [item.sku_id for item in data.items]
        sku_index = await self.b2b_client.get_skus_info(sku_ids)
        missing = [sid for sid in sku_ids if sid not in sku_index]
        if missing:
            failed_items = [
                {'sku_id': str(sid), 'requested': 0, 'available': 0, 'reason': 'SKU_NOT_FOUND'} for sid in missing
            ]
            raise ReserveFailedError(failed_items=failed_items)

        # 2. Reserve в B2B (all-or-nothing). 409 → ReserveFailedError, 5xx → B2BUnavailableError.
        await self.b2b_client.reserve(
            idempotency_key=data.idempotency_key,
            items=[{'sku_id': str(it.sku_id), 'quantity': it.quantity} for it in data.items],
        )

        # 3. Собрать OrderItem-данные с зафиксированными ценами/названиями.
        order_item_data, total_amount = self._build_items_with_snapshot(data, sku_index)

        order_create = OrderCreateSchema(
            user_id=current_user.id,
            status=OrderStatus.PAID.value,
            total_amount=total_amount,
            idempotency_key=data.idempotency_key,
            address_id=data.address_id,
            payment_method_id=data.payment_method_id,
        )

        try:
            order_schema, item_models = await self.order_repository.create_with_items(order_create, order_item_data)
        except IntegrityError:
            # Гонка: параллельный запрос с тем же idempotency_key успел создать.
            # Повторно фетчим — гарантировано в БД.
            duplicated = await self.order_repository.get_by_idempotency_key(data.idempotency_key)
            assert duplicated is not None, 'IntegrityError without matching row?'
            response = await self._assemble_response(duplicated)
            return response, False

        return self._build_response_from_models(order_schema, item_models), True

    def _build_items_with_snapshot(
        self,
        data: CheckoutRequestSchema,
        sku_index: dict,
    ) -> tuple[list[OrderItemCreateSchema], int]:
        items: list[OrderItemCreateSchema] = []
        total = 0
        for req_item in data.items:
            raw = sku_index[req_item.sku_id]
            unit_price = int(raw.get('price', 0))
            product_id = raw.get('product_id')
            assert product_id is not None, 'B2B sku payload missing product_id'
            product_title = raw.get('product_title') or raw.get('title') or ''
            sku_name = raw.get('name') or raw.get('sku_name') or raw.get('title') or ''
            line_total = unit_price * req_item.quantity
            total += line_total
            items.append(
                OrderItemCreateSchema(
                    order_id=req_item.sku_id,  # placeholder, заменит репозиторий
                    sku_id=req_item.sku_id,
                    product_id=product_id,
                    product_title=str(product_title),
                    sku_name=str(sku_name),
                    quantity=req_item.quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )
        return items, total

    @staticmethod
    def _build_response_from_models(order_schema, item_models) -> OrderResponseSchema:
        return OrderResponseSchema(
            id=order_schema.id,
            user_id=order_schema.user_id,
            status=order_schema.status,
            items=[
                OrderItemResponseSchema(
                    id=im.id,
                    sku_id=im.sku_id,
                    product_id=im.product_id,
                    product_title=im.product_title,
                    sku_name=im.sku_name,
                    quantity=im.quantity,
                    unit_price=im.unit_price,
                    line_total=im.line_total,
                )
                for im in item_models
            ],
            total_amount=order_schema.total_amount,
            delivery_address=order_schema.delivery_address,
            address_id=order_schema.address_id,
            payment_method_id=order_schema.payment_method_id,
            created_at=order_schema.created_at,
            updated_at=order_schema.updated_at,
        )

    async def _assemble_response(self, order_schema) -> OrderResponseSchema:
        item_schemas = await self.order_item_repository.list_for_order(order_schema.id)
        return OrderResponseSchema(
            id=order_schema.id,
            user_id=order_schema.user_id,
            status=order_schema.status,
            items=[
                OrderItemResponseSchema(
                    id=it.id,
                    sku_id=it.sku_id,
                    product_id=it.product_id,
                    product_title=it.product_title,
                    sku_name=it.sku_name,
                    quantity=it.quantity,
                    unit_price=it.unit_price,
                    line_total=it.line_total,
                )
                for it in item_schemas
            ],
            total_amount=order_schema.total_amount,
            delivery_address=order_schema.delivery_address,
            address_id=order_schema.address_id,
            payment_method_id=order_schema.payment_method_id,
            created_at=order_schema.created_at,
            updated_at=order_schema.updated_at,
        )
