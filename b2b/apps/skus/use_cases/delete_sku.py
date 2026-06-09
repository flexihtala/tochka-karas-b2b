"""US-B2B-12: удаление SKU продавцом.

Бизнес-правила (см. neomarket-canon/flows/b2b-flows.md#delete-sku):

Порядок гардов (важен — менять нельзя):
    1. SKU существует → иначе 404 NOT_FOUND.
    2. ownership: sku.product.seller_id == JWT.user_id → иначе 403 NOT_OWNER.
    3. product.status == HARD_BLOCKED → 403 HARD_BLOCKED.
    4. sku.reserved_quantity > 0 → 409 HAS_ACTIVE_RESERVES (нельзя удалить SKU
       с активными резервами B2C).
    5. hard-delete SKU из БД.

Side-effects (только при успешном удалении):
    - Если это был последний SKU товара И product.status == ON_MODERATION,
      то product.status → CREATED + outbox DELETED (target=moderation).
    - Если SKU был на MODERATED-товаре и его active_quantity > 0 →
      outbox SKU_OUT_OF_STOCK (target=b2c) с sku_id (B2C пометит cart_items).

ADR: ordering of guardrails.
    Выбран вариант "линейные ранние возвраты внутри __call__".
    Альтернативы:
      (a) отдельные методы (`_check_ownership`, `_check_status`, ...) с ранними
          возвратами — добавляют шум, но не повышают читаемость на 4 проверках;
      (b) единый `_validate_deletion` с цепочкой if-raise — эквивалентен текущему,
          лишь даёт ещё один уровень отступа;
      (c) встроить в сериализатор — нельзя, т.к. некоторые гарды требуют доступа
          к данным БД (product.status, sku.reserved_quantity), сериализатор
          их не видит.
    Критерий выбора: читаемость + защита от перестановки. Линейная цепочка ниже
    самодокументируема (комментарии по канону), визуальный порядок совпадает
    с порядком в спецификации, риск незаметной перестановки минимален: любая
    подмена в diff-обзоре видна с одного взгляда. На 4-х проверках выделение
    в private-методы было бы over-engineering.
"""

from uuid import UUID, uuid4

from apps.outbox.repositories import B2BOutboxRepository
from apps.products.enums import ProductStatus
from apps.products.repositories import ProductRepository
from apps.products.schemas.db import ProductUpdateSchema
from apps.skus.errors import (
    SKUHardBlockedError,
    SKUHasActiveReservesError,
    SKUNotFoundError,
    SKUNotOwnerError,
)
from apps.skus.repositories import SKURepository
from apps.skus.schemas.db import SKUReadSchema
from shared.auth_lib import AuthenticatedUserSchema
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName


class DeleteSKUUseCase:
    def __init__(
        self,
        sku_repository: SKURepository,
        product_repository: ProductRepository,
        outbox_repository: B2BOutboxRepository,
    ):
        self.sku_repository = sku_repository
        self.product_repository = product_repository
        self.outbox_repository = outbox_repository

    async def __call__(self, sku_id: UUID, current_user: AuthenticatedUserSchema) -> None:
        sku = await self.sku_repository.get_or_none(sku_id)
        if sku is None:
            raise SKUNotFoundError()

        product = await self.product_repository.get_or_none(sku.product_id)
        # FK ondelete=CASCADE гарантирует, что product существует — но защищаемся
        # от рассинхрона данных.
        if product is None:
            raise SKUNotFoundError()

        if product.seller_id != current_user.id:
            raise SKUNotOwnerError(message='SKU does not belong to the authenticated seller')

        if product.status == ProductStatus.HARD_BLOCKED:
            raise SKUHardBlockedError(message='Cannot delete SKU of hard-blocked product')

        if sku.reserved_quantity > 0:
            raise SKUHasActiveReservesError()

        deleted = await self.sku_repository.delete(sku_id)
        if not deleted:
            # Возможна гонка: между get_or_none и delete кто-то уже удалил SKU.
            # Трактуем как NOT_FOUND.
            raise SKUNotFoundError()

        await self._maybe_emit_side_effects(sku, product.status)

    async def _maybe_emit_side_effects(self, sku: SKUReadSchema, product_status: ProductStatus) -> None:
        """Эффекты выполняются только при успешном удалении SKU.

        1. Последний SKU товара + product.status == ON_MODERATION:
            - product.status → CREATED (модерировать больше нечего)
            - outbox DELETED в moderation (Moderation удалит запись из очереди)

        2. SKU имел active_quantity > 0 + product.status == MODERATED:
            - outbox SKU_OUT_OF_STOCK в b2c (B2C пометит cart_items как unavailable).
        """
        remaining = await self.sku_repository.count_by_product(sku.product_id)

        if remaining == 0 and product_status == ProductStatus.ON_MODERATION:
            await self.product_repository.update(ProductUpdateSchema(id=sku.product_id, status=ProductStatus.CREATED))
            await self.outbox_repository.enqueue_in_new_transaction(
                OutboxEnqueueSchema(
                    idempotency_key=uuid4(),
                    event_type='DELETED',
                    target_service=ServiceName.MODERATION,
                    payload={
                        'product_id': str(sku.product_id),
                    },
                )
            )

        if product_status == ProductStatus.MODERATED and sku.active_quantity > 0:
            await self.outbox_repository.enqueue_in_new_transaction(
                OutboxEnqueueSchema(
                    idempotency_key=uuid4(),
                    event_type='SKU_OUT_OF_STOCK',
                    target_service=ServiceName.B2C,
                    payload={
                        'sku_id': str(sku.id),
                        'product_id': str(sku.product_id),
                    },
                )
            )
