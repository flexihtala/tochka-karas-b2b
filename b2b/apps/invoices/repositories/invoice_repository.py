from apps.invoices.models import Invoice
from apps.invoices.schemas.db import (
    InvoiceCreateSchema,
    InvoiceReadSchema,
    InvoiceUpdateSchema,
)
from db import DBCrudRepository


class InvoiceRepository(DBCrudRepository[Invoice, InvoiceCreateSchema, InvoiceReadSchema, InvoiceUpdateSchema]):
    pass
