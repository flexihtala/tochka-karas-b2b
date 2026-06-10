import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.invoices.enums import InvoiceStatus
from db import Base, IDMixin, TimestampMixin


class Invoice(IDMixin, TimestampMixin, Base):
    __tablename__ = 'invoices'

    seller_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('users.id'),
        index=True,
        nullable=False,
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        String(32),
        nullable=False,
        default=InvoiceStatus.CREATED,
        server_default=InvoiceStatus.CREATED.value,
    )

    items: Mapped[list['InvoiceItem']] = relationship(  # noqa: F821
        'InvoiceItem',
        cascade='all, delete-orphan',
        lazy='selectin',
    )

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        seller_id: uuid.UUID,
        status: InvoiceStatus = InvoiceStatus.CREATED,
    ):
        if id is not None:
            self.id = id
        self.seller_id = seller_id
        self.status = status
