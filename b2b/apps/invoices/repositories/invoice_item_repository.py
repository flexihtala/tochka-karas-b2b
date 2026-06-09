from uuid import UUID

from sqlalchemy import select

from apps.invoices.models import InvoiceItem
from apps.invoices.schemas.db import (
    InvoiceItemCreateSchema,
    InvoiceItemReadSchema,
    InvoiceItemUpdateSchema,
)
from db import DBCrudRepository


class InvoiceItemRepository(
    DBCrudRepository[InvoiceItem, InvoiceItemCreateSchema, InvoiceItemReadSchema, InvoiceItemUpdateSchema]
):
    async def list_by_invoice(self, invoice_id: UUID) -> list[InvoiceItemReadSchema]:
        query = select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
        async with self.session_manager.get_session() as session:
            result = (await session.execute(query)).scalars().all()
        return [self.model_validate(m) for m in result]
