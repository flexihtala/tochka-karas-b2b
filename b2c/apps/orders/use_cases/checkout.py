"""US-ORD-01: POST /api/v1/orders — checkout (cart-based, spec OpenAPI).

Бизнес-правила (см. neomarket-canon/flows/b2c-orders-flows.md#b2c-9-checkout):

- **Idempotency**: UNIQUE на orders.idempotency_key. Повтор → возврат существующего
  заказа со статусом 200 (не 201). Гонку обрабатываем double-check: SELECT перед
  INSERT, IntegrityError на INSERT → повторный SELECT (см. ADR).
- **Items берутся из КОРЗИНЫ пользователя** (cart-based, расхождение со старой
  canon-моделью "items в теле"; user выбрал полную совместимость со spec).
- Снапшот цен/наличия — `POST /api/v1/public/products/batch` (JSON-массив товаров).
- Валидация: пустая корзина / недоступный SKU / active_quantity < quantity → 422
  CART_INVALID. Расхождение items_snapshot с корзиной → 422.
- **Reserve в B2B** (all-or-nothing) с order_id + idempotency_key. 409 → 409
  RESERVE_FAILED, 5xx/timeout → 503 B2B_UNAVAILABLE.
- На success: создать Order(status=PAID) + OrderItem'ы с FIXED snapshot
  (unit_price, product_title, sku_name, product_id).
- Корзину сервер НЕ чистит — фронт вызывает DELETE /api/v1/cart после 201.
"""

from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from apps.addresses.repositories import AddressRepository
from apps.addresses.schemas.response import AddressResponseSchema
from apps.cart.repositories import CartItemRepository, CartRepository
from apps.cart.schemas.db import CartItemReadSchema
from apps.orders.b2b_client import B2BInventoryClient
from apps.orders.enums import OrderStatus
from apps.orders.errors import (
    CartInvalidError,
    InvalidAddressError,
    InvalidPaymentMethodError,
)
from apps.orders.repositories import OrderItemRepository, OrderRepository
from apps.orders.schemas.db import OrderCreateSchema, OrderItemCreateSchema, OrderReadSchema
from apps.orders.schemas.request import OrderCreateRequestSchema
from apps.orders.schemas.response import OrderItemResponseSchema, OrderResponseSchema
from apps.orders.use_cases.response_assembler import assemble_order_response
from apps.payment_methods.repositories import PaymentMethodRepository
from apps.payment_methods.schemas.response import PaymentMethodResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


class _SnapshotLine:
    """Промежуточный снапшот одной позиции (между обогащением и записью в БД)."""

    __slots__ = ('sku_id', 'product_id', 'product_title', 'sku_name', 'unit_price', 'quantity', 'line_total')

    def __init__(
        self,
        *,
        sku_id: UUID,
        product_id: UUID,
        product_title: str,
        sku_name: str,
        unit_price: int,
        quantity: int,
    ):
        self.sku_id = sku_id
        self.product_id = product_id
        self.product_title = product_title
        self.sku_name = sku_name
        self.unit_price = unit_price
        self.quantity = quantity
        self.line_total = unit_price * quantity


class CheckoutUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        order_item_repository: OrderItemRepository,
        b2b_client: B2BInventoryClient,
        cart_repository: CartRepository,
        cart_item_repository: CartItemRepository,
        address_repository: AddressRepository,
        payment_method_repository: PaymentMethodRepository,
    ):
        self.order_repository = order_repository
        self.order_item_repository = order_item_repository
        self.b2b_client = b2b_client
        self.cart_repository = cart_repository
        self.cart_item_repository = cart_item_repository
        self.address_repository = address_repository
        self.payment_method_repository = payment_method_repository

    async def __call__(
        self,
        *,
        idempotency_key: UUID,
        data: OrderCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> tuple[OrderResponseSchema, bool]:
        """Возвращает (order_response, created_flag).

        created_flag=False → идемпотентный повтор → router отдаст 200.
        created_flag=True  → заказ создан в этом вызове → 201.
        """
        # 1. Idempotency: уже создавали?
        existing = await self.order_repository.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return await self._assemble_response(existing), False

        # 2. Загрузить корзину пользователя.
        cart = await self.cart_repository.get_by_user(current_user.id)
        cart_items = await self.cart_item_repository.list_by_cart(cart.id) if cart is not None else []
        if not cart_items:
            raise CartInvalidError(issues=[{'type': 'OUT_OF_STOCK', 'message': 'Корзина пуста'}])

        # 3. Обогатить + валидировать снапшот через B2B batch.
        lines = await self._enrich_and_validate(cart_items, data.items_snapshot)
        total_amount = sum(line.line_total for line in lines)

        # 4. Валидация адреса и способа оплаты (владение) — ДО резерва: дешёвые
        #    локальные проверки должны фейлить быстро, не оставляя висячий резерв в B2B.
        address = await self.address_repository.get_or_none(data.address_id)
        if address is None or address.buyer_id != current_user.id:
            raise InvalidAddressError()
        payment_method = await self.payment_method_repository.get_or_none(data.payment_method_id)
        if payment_method is None or payment_method.buyer_id != current_user.id:
            raise InvalidPaymentMethodError()

        # 5. order_id генерируем ДО резерва — B2B требует его в payload.
        order_id = uuid4()

        # 6. Reserve all-or-nothing. 409 → ReserveFailedError, 5xx/timeout → B2BUnavailableError.
        #    Выполняется последним из side-effect'ов: всё дешёвое уже провалидировано.
        await self.b2b_client.reserve(
            idempotency_key=idempotency_key,
            order_id=order_id,
            items=[{'sku_id': str(line.sku_id), 'quantity': line.quantity} for line in lines],
        )

        # 7. Создать Order(status=PAID) + OrderItem'ы (атомарно). Гонка по UNIQUE → повтор.
        order_create = OrderCreateSchema(
            id=order_id,
            user_id=current_user.id,
            status=OrderStatus.PAID.value,
            total_amount=total_amount,
            idempotency_key=idempotency_key,
            address_id=data.address_id,
            payment_method_id=data.payment_method_id,
            comment=data.comment,
        )
        item_creates = [
            OrderItemCreateSchema(
                order_id=order_id,
                sku_id=line.sku_id,
                product_id=line.product_id,
                product_title=line.product_title,
                sku_name=line.sku_name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=line.line_total,
            )
            for line in lines
        ]
        try:
            order_schema, _ = await self.order_repository.create_with_items(order_create, item_creates)
        except IntegrityError:
            # Гонка: параллельный запрос с тем же idempotency_key успел создать.
            duplicated = await self.order_repository.get_by_idempotency_key(idempotency_key)
            assert duplicated is not None, 'IntegrityError without matching row?'
            return await self._assemble_response(duplicated), False

        return self._build_response(order_schema, lines, address, payment_method), True

    async def _enrich_and_validate(
        self,
        cart_items: list[CartItemReadSchema],
        items_snapshot: list | None,
    ) -> list[_SnapshotLine]:
        """Обогащает позиции корзины данными B2B и валидирует доступность.

        Issues (формат spec CartValidationIssue) собираются по всем позициям; любой
        issue → CartInvalidError (422). Если задан items_snapshot — дополнительно
        сверяет sku set / quantity / unit_price с актуальной корзиной.
        """
        product_ids = sorted({item.product_id for item in cart_items if item.product_id is not None})
        sku_index = await self.b2b_client.get_products_batch(product_ids)

        issues: list[dict] = []
        lines: list[_SnapshotLine] = []
        for item in cart_items:
            raw = sku_index.get(item.sku_id)
            if raw is None:
                issues.append(
                    {
                        'sku_id': str(item.sku_id),
                        'type': 'PRODUCT_DELETED',
                        'message': 'Товар недоступен',
                    }
                )
                continue
            active_quantity = int(raw['active_quantity'])
            if active_quantity < item.quantity:
                issues.append(
                    {
                        'sku_id': str(item.sku_id),
                        'type': 'OUT_OF_STOCK' if active_quantity == 0 else 'QUANTITY_REDUCED',
                        'message': 'Недостаточно товара в наличии',
                        'old_value': item.quantity,
                        'new_value': active_quantity,
                    }
                )
                continue
            lines.append(
                _SnapshotLine(
                    sku_id=item.sku_id,
                    product_id=raw['product_id'],
                    product_title=raw['product_title'],
                    sku_name=raw['sku_name'],
                    unit_price=int(raw['price']),
                    quantity=item.quantity,
                )
            )

        self._check_snapshot(lines, items_snapshot, issues)

        if issues:
            raise CartInvalidError(issues=issues)
        return lines

    @staticmethod
    def _check_snapshot(
        lines: list[_SnapshotLine],
        items_snapshot: list | None,
        issues: list[dict],
    ) -> None:
        """Сверяет переданный клиентом items_snapshot с актуальной корзиной.

        Расхождение по составу SKU, количеству или цене → issue PRICE_CHANGED.
        Вызывается только когда snapshot передан (защита от гонок, spec).
        """
        if items_snapshot is None:
            return
        live_by_sku = {line.sku_id: line for line in lines}
        snapshot_by_sku = {snap.sku_id: snap for snap in items_snapshot}
        if set(live_by_sku) != set(snapshot_by_sku):
            issues.append({'type': 'PRICE_CHANGED', 'message': 'Состав корзины изменился'})
            return
        for sku_id, snap in snapshot_by_sku.items():
            line = live_by_sku[sku_id]
            if line.quantity != snap.quantity or line.unit_price != snap.unit_price:
                issues.append(
                    {
                        'sku_id': str(sku_id),
                        'type': 'PRICE_CHANGED',
                        'message': 'Цена или количество изменились',
                        'old_value': snap.unit_price,
                        'new_value': line.unit_price,
                    }
                )

    @staticmethod
    def _build_response(
        order: OrderReadSchema,
        lines: list[_SnapshotLine],
        address: AddressResponseSchema | object,
        payment_method: PaymentMethodResponseSchema | object | None,
    ) -> OrderResponseSchema:
        subtotal = sum(line.line_total for line in lines)
        return OrderResponseSchema(
            id=order.id,
            buyer_id=order.user_id,
            status=order.status,
            items=[
                OrderItemResponseSchema(
                    sku_id=line.sku_id,
                    product_id=line.product_id,
                    name=f'{line.product_title} {line.sku_name}'.strip(),
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    line_total=line.line_total,
                )
                for line in lines
            ],
            subtotal=subtotal,
            total=order.total_amount,
            address=AddressResponseSchema.model_validate(address),
            payment_method=(
                PaymentMethodResponseSchema.model_validate(payment_method) if payment_method is not None else None
            ),
            comment=order.comment,
            created_at=order.created_at,
            paid_at=order.created_at if order.status == OrderStatus.PAID.value else None,
        )

    async def _assemble_response(self, order: OrderReadSchema) -> OrderResponseSchema:
        """Собирает ответ из персистентного заказа (идемпотентный повтор).

        Делегирует в общий ассемблер (тот же, что использует cancel), чтобы форма
        ответа двух эндпоинтов не расходилась.
        """
        return await assemble_order_response(
            order,
            order_item_repository=self.order_item_repository,
            address_repository=self.address_repository,
            payment_method_repository=self.payment_method_repository,
        )
