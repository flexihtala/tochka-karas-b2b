"""US-B2B-04: мягкое удаление товара продавцом.

Бизнес-правила (см. neomarket-canon/flows/b2b-flows.md#delete-product):

- Auth: SELLER (роль проверяется на уровне роутера).
- Ownership check (защита от IDOR): product.seller_id == JWT.user_id, иначе 403 NOT_OWNER.
- product.status == HARD_BLOCKED -> 403 HARD_BLOCKED.
- product.deleted == True -> 400 ALREADY_DELETED (повторное удаление запрещено).
- Удаление мягкое: deleted = true. Строка НЕ удаляется физически (нужна история).
- Каскадные события через outbox (см. ADR-04: оба события через outbox для consistency-at-least-once):
    1. DELETED -> moderation. payload: {product_id, seller_id}.
    2. PRODUCT_DELETED -> b2c. payload: {product_id, sku_ids}.
- product не должен попадать в seller list по умолчанию (см. repository.list_by_seller).
"""

from uuid import UUID, uuid4

from apps.outbox.repositories import B2BOutboxRepository
from apps.products.enums import ProductStatus
from apps.products.errors import (
    ProductAlreadyDeletedError,
    ProductHardBlockedError,
    ProductNotFoundError,
    ProductNotOwnerError,
)
from apps.products.repositories import ProductRepository
from apps.products.schemas.db import ProductReadSchema, ProductUpdateSchema
from apps.skus.repositories import SKURepository
from shared.auth_lib import AuthenticatedUserSchema
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName


class DeleteProductUseCase:
    def __init__(
        self,
        product_repository: ProductRepository,
        sku_repository: SKURepository,
        outbox_repository: B2BOutboxRepository,
    ):
        self.product_repository = product_repository
        self.sku_repository = sku_repository
        self.outbox_repository = outbox_repository

    async def __call__(self, product_id: UUID, current_user: AuthenticatedUserSchema) -> None:
        product = await self._load_product(product_id, current_user)

        await self.product_repository.update(ProductUpdateSchema(id=product.id, deleted=True))

        sku_ids = await self.sku_repository.list_ids_by_product(product.id)
        await self._enqueue_moderation_event(product)
        await self._enqueue_b2c_event(product, sku_ids)

    async def _load_product(self, product_id: UUID, current_user: AuthenticatedUserSchema) -> ProductReadSchema:
        product = await self.product_repository.get_or_none(product_id)
        if product is None:
            raise ProductNotFoundError()
        if product.seller_id != current_user.id:
            raise ProductNotOwnerError()
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ProductHardBlockedError()
        if product.deleted:
            raise ProductAlreadyDeletedError()
        return product

    async def _enqueue_moderation_event(self, product: ProductReadSchema) -> None:
        await self.outbox_repository.enqueue_in_new_transaction(
            OutboxEnqueueSchema(
                idempotency_key=uuid4(),
                event_type='DELETED',
                target_service=ServiceName.MODERATION,
                payload={
                    'product_id': str(product.id),
                    'seller_id': str(product.seller_id),
                },
            )
        )

    async def _enqueue_b2c_event(self, product: ProductReadSchema, sku_ids: list[UUID]) -> None:
        await self.outbox_repository.enqueue_in_new_transaction(
            OutboxEnqueueSchema(
                idempotency_key=uuid4(),
                event_type='PRODUCT_DELETED',
                target_service=ServiceName.B2C,
                payload={
                    'product_id': str(product.id),
                    'sku_ids': [str(sku_id) for sku_id in sku_ids],
                },
            )
        )
