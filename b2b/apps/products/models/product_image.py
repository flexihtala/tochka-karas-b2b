import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, IDMixin, TimestampMixin


class ProductImage(IDMixin, TimestampMixin, Base):
    __tablename__ = 'product_images'

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('products.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    ordering: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        product_id: uuid.UUID,
        url: str,
        ordering: int = 0,
    ):
        if id is not None:
            self.id = id
        self.product_id = product_id
        self.url = url
        self.ordering = ordering
