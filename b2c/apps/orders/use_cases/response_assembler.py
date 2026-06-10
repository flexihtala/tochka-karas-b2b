"""Сборка OrderResponse из персистентного заказа.

Единый ассемблер ответа: и checkout (идемпотентный повтор), и cancel строят
ответ через `assemble_order_response`, поэтому форма ответа двух эндпоинтов
никогда не расходится. Подтягивает items (снапшот), адрес и способ оплаты по
сохранённым в заказе id; если адрес удалён после оформления — отдаёт минимальную
заглушку (spec требует non-null `address`).
"""

from apps.addresses.repositories import AddressRepository
from apps.addresses.schemas.response import AddressResponseSchema
from apps.orders.enums import OrderStatus
from apps.orders.repositories import OrderItemRepository
from apps.orders.schemas.db import OrderReadSchema
from apps.orders.schemas.response import OrderItemResponseSchema, OrderResponseSchema
from apps.payment_methods.repositories import PaymentMethodRepository
from apps.payment_methods.schemas.response import PaymentMethodResponseSchema


def _address_response(order: OrderReadSchema, address: object | None) -> AddressResponseSchema:
    if address is not None:
        return AddressResponseSchema.model_validate(address)
    # Адрес удалён после оформления — отдаём минимальную заглушку (spec требует address).
    return AddressResponseSchema(
        id=order.address_id or order.id,
        buyer_id=order.user_id,
        country='',
        city='',
        street=order.delivery_address or '',
        postal_code='',
        comment=None,
        is_default=False,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


async def assemble_order_response(
    order: OrderReadSchema,
    *,
    order_item_repository: OrderItemRepository,
    address_repository: AddressRepository,
    payment_method_repository: PaymentMethodRepository,
) -> OrderResponseSchema:
    """Собирает spec OrderResponse из сохранённого заказа.

    `status`/`cancel_reason` берутся из переданного (уже обновлённого) заказа, так
    что cancel-ответ отражает актуальный статус и причину отмены. `paid_at`
    проставляется в created_at, когда заказ оплачен (status == PAID).
    """
    items = await order_item_repository.list_for_order(order.id)
    subtotal = sum(it.line_total for it in items)

    address = None
    if order.address_id is not None:
        address = await address_repository.get_or_none(order.address_id)
    payment_method = None
    if order.payment_method_id is not None:
        payment_method = await payment_method_repository.get_or_none(order.payment_method_id)

    return OrderResponseSchema(
        id=order.id,
        buyer_id=order.user_id,
        status=order.status,
        items=[
            OrderItemResponseSchema(
                sku_id=it.sku_id,
                product_id=it.product_id,
                name=f'{it.product_title} {it.sku_name}'.strip(),
                quantity=it.quantity,
                unit_price=it.unit_price,
                line_total=it.line_total,
            )
            for it in items
        ],
        subtotal=subtotal,
        total=order.total_amount,
        address=_address_response(order, address),
        payment_method=(
            PaymentMethodResponseSchema.model_validate(payment_method) if payment_method is not None else None
        ),
        comment=order.comment,
        cancel_reason=order.cancel_reason,
        created_at=order.created_at,
        paid_at=order.created_at if order.status == OrderStatus.PAID.value else None,
    )
