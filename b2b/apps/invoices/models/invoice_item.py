import uuid

from sqlalchemy import ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, IDMixin, TimestampMixin


class InvoiceItem(IDMixin, TimestampMixin, Base):
    __tablename__ = 'invoice_items'

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('invoices.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('skus.id'),
        index=True,
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default='0',
    )

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        invoice_id: uuid.UUID,
        sku_id: uuid.UUID,
        quantity: int,
        accepted_quantity: int = 0,
    ):
        if id is not None:
            self.id = id
        self.invoice_id = invoice_id
        self.sku_id = sku_id
        self.quantity = quantity
        self.accepted_quantity = accepted_quantity
