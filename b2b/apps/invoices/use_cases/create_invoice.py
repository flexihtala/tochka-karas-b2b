"""US-B2B-06: создание накладной продавцом.

Бизнес-правила (см. neomarket-canon/flows/b2b-flows.md#create-invoice):

- Требуется минимум 1 позиция → иначе 400 INVALID_REQUEST.
- Для КАЖДОГО ``sku_id`` в ``items``:
    * SKU должен существовать → иначе 400 INVALID_REQUEST.
    * SKU.product.seller_id == JWT.user_id → иначе 403 NOT_OWNER.
    * SKU.product.status == MODERATED → иначе 400 INVALID_REQUEST
      ("Invoice can only be created for MODERATED products"). Любые
      другие статусы (CREATED / ON_MODERATION / BLOCKED / HARD_BLOCKED)
      — отказ.

Накладная создаётся со статусом CREATED, ``accepted_quantity`` каждой
позиции инициализируется нулём (приёмка — отдельный admin-flow,
не часть этой задачи).

Проверка владельца **должна** идти ДО проверки статуса MODERATED:
"NOT_OWNER" — это сигнал об IDOR-попытке и должен иметь приоритет над
"не-модератед" (последнее раскрывает факт существования SKU чужого продавца
в категории, что для атакующего полезная информация).
"""

from apps.invoices.errors import (
    InvoiceEmptyItemsError,
    InvoiceNotOwnerError,
    InvoiceSKUNotFoundError,
    InvoiceSKUNotModeratedError,
)
from apps.invoices.repositories import (
    InvoiceItemRepository,
    InvoiceRepository,
)
from apps.invoices.schemas.db import (
    InvoiceCreateSchema,
    InvoiceItemCreateSchema,
)
from apps.invoices.schemas.request import InvoiceCreateRequestSchema
from apps.invoices.schemas.response import (
    InvoiceItemResponseSchema,
    InvoiceResponseSchema,
)
from apps.products.enums import ProductStatus
from apps.products.repositories import ProductRepository
from apps.skus.repositories import SKURepository
from shared.auth_lib import AuthenticatedUserSchema


class CreateInvoiceUseCase:
    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        invoice_item_repository: InvoiceItemRepository,
        sku_repository: SKURepository,
        product_repository: ProductRepository,
    ):
        self.invoice_repository = invoice_repository
        self.invoice_item_repository = invoice_item_repository
        self.sku_repository = sku_repository
        self.product_repository = product_repository

    async def __call__(
        self,
        data: InvoiceCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> InvoiceResponseSchema:
        if not data.items:
            raise InvoiceEmptyItemsError()

        # Валидируем все позиции ДО создания накладной — fail-fast на первой
        # проблемной позиции, чтобы не плодить мусорные записи в БД.
        for item in data.items:
            await self._validate_item(item.sku_id, current_user)

        invoice = await self.invoice_repository.create(InvoiceCreateSchema(seller_id=current_user.id))

        created_items = [
            await self.invoice_item_repository.create(
                InvoiceItemCreateSchema(
                    invoice_id=invoice.id,
                    sku_id=item.sku_id,
                    quantity=item.quantity,
                    accepted_quantity=0,
                )
            )
            for item in data.items
        ]

        return InvoiceResponseSchema(
            id=invoice.id,
            seller_id=invoice.seller_id,
            status=invoice.status,
            items=[
                InvoiceItemResponseSchema(
                    id=ii.id,
                    sku_id=ii.sku_id,
                    quantity=ii.quantity,
                    accepted_quantity=ii.accepted_quantity,
                )
                for ii in created_items
            ],
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
        )

    async def _validate_item(self, sku_id, current_user: AuthenticatedUserSchema) -> None:
        sku = await self.sku_repository.get_or_none(sku_id)
        if sku is None:
            raise InvoiceSKUNotFoundError()

        product = await self.product_repository.get_or_none(sku.product_id)
        # Дефенсивно: если sku есть, а product исчез — относимся как к "SKU не пригоден".
        if product is None:
            raise InvoiceSKUNotFoundError()

        if product.seller_id != current_user.id:
            raise InvoiceNotOwnerError()

        if product.status != ProductStatus.MODERATED:
            raise InvoiceSKUNotModeratedError()
