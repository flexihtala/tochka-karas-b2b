from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.invoices.enums import InvoiceStatus
from apps.invoices.schemas.db import (
    InvoiceCreateSchema,
    InvoiceItemCreateSchema,
    InvoiceItemReadSchema,
    InvoiceReadSchema,
    InvoiceUpdateSchema,
)
from apps.products.enums import ProductStatus
from apps.products.schemas.db import ProductReadSchema
from apps.skus.schemas.db import SKUReadSchema


class FakeInvoiceRepository:
    def __init__(self):
        self.by_id: dict[UUID, InvoiceReadSchema] = {}
        self.created: list[InvoiceCreateSchema] = []
        self.updated: list[InvoiceUpdateSchema] = []

    async def create(self, data: InvoiceCreateSchema) -> InvoiceReadSchema:
        self.created.append(data)
        invoice_id = data.id or uuid4()
        now = datetime.now(UTC)
        invoice = InvoiceReadSchema(
            id=invoice_id,
            seller_id=data.seller_id,
            status=data.status,
            created_at=now,
            updated_at=now,
        )
        self.by_id[invoice_id] = invoice
        return invoice

    async def get_or_none(self, id_: UUID) -> InvoiceReadSchema | None:
        return self.by_id.get(id_)


class FakeInvoiceItemRepository:
    def __init__(self):
        self.created: list[InvoiceItemCreateSchema] = []
        self.by_id: dict[UUID, InvoiceItemReadSchema] = {}

    async def create(self, data: InvoiceItemCreateSchema) -> InvoiceItemReadSchema:
        self.created.append(data)
        item_id = data.id or uuid4()
        now = datetime.now(UTC)
        item = InvoiceItemReadSchema(
            id=item_id,
            invoice_id=data.invoice_id,
            sku_id=data.sku_id,
            quantity=data.quantity,
            accepted_quantity=data.accepted_quantity,
            created_at=now,
            updated_at=now,
        )
        self.by_id[item_id] = item
        return item

    async def list_by_invoice(self, invoice_id: UUID) -> list[InvoiceItemReadSchema]:
        return [i for i in self.by_id.values() if i.invoice_id == invoice_id]


class FakeSKURepositoryReadable:
    """SKU-фейк для тестов накладных: только get_or_none."""

    def __init__(self):
        self.by_id: dict[UUID, SKUReadSchema] = {}

    def add(
        self,
        *,
        id: UUID | None = None,
        product_id: UUID | None = None,
        name: str = '256GB Black',
        price: int = 12_999_000,
        cost_price: int = 9_500_000,
        discount: int = 0,
        article: str | None = None,
        active_quantity: int = 0,
        reserved_quantity: int = 0,
        stock_quantity: int | None = None,
    ) -> UUID:
        sku_id = id or uuid4()
        now = datetime.now(UTC)
        sku = SKUReadSchema(
            id=sku_id,
            product_id=product_id or uuid4(),
            name=name,
            price=price,
            cost_price=cost_price,
            discount=discount,
            article=article,
            active_quantity=active_quantity,
            reserved_quantity=reserved_quantity,
            # Канонический инвариант: stock = active + reserved (US-B2B-08).
            stock_quantity=stock_quantity if stock_quantity is not None else active_quantity + reserved_quantity,
            created_at=now,
            updated_at=now,
        )
        self.by_id[sku_id] = sku
        return sku_id

    async def get_or_none(self, id_: UUID) -> SKUReadSchema | None:
        return self.by_id.get(id_)


class FakeProductRepositoryReadable:
    """Product-фейк для тестов накладных: только get_or_none."""

    def __init__(self):
        self.by_id: dict[UUID, ProductReadSchema] = {}

    def add(
        self,
        *,
        id: UUID | None = None,
        seller_id: UUID | None = None,
        category_id: UUID | None = None,
        title: str = 'iPhone 15 Pro Max',
        slug: str = 'iphone-15-pro-max',
        description: str = 'Флагман Apple',
        status: ProductStatus = ProductStatus.MODERATED,
        deleted: bool = False,
    ) -> UUID:
        product_id = id or uuid4()
        now = datetime.now(UTC)
        product = ProductReadSchema(
            id=product_id,
            seller_id=seller_id or uuid4(),
            category_id=category_id or uuid4(),
            title=title,
            slug=slug,
            description=description,
            status=status,
            deleted=deleted,
            blocking_reason_id=None,
            moderator_comment=None,
            created_at=now,
            updated_at=now,
        )
        self.by_id[product_id] = product
        return product_id

    async def get_or_none(self, id_: UUID) -> ProductReadSchema | None:
        return self.by_id.get(id_)


__all__ = [
    'FakeInvoiceItemRepository',
    'FakeInvoiceRepository',
    'FakeProductRepositoryReadable',
    'FakeSKURepositoryReadable',
    'InvoiceStatus',
]
