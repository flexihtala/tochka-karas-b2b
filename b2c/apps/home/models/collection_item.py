import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, IDMixin, TimestampMixin


class CollectionItem(IDMixin, TimestampMixin, Base):
    """Привязка товара (uuid) к подборке.

    Бизнес-правила (US-CART-05):
    - product_id хранится как uuid, БЕЗ FK на products (продукты живут в b2b).
      Это намеренно — см. ADR в PR.
    - UNIQUE (collection_id, product_id) — один товар не дублируется в подборке.
    - ordering управляет порядком внутри подборки.
    """

    __tablename__ = 'collection_items'
    __table_args__ = (UniqueConstraint('collection_id', 'product_id', name='uq_collection_items_collection_product'),)

    collection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('collections.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ordering: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        collection_id: uuid.UUID,
        product_id: uuid.UUID,
        ordering: int = 0,
    ):
        if id is not None:
            self.id = id
        self.collection_id = collection_id
        self.product_id = product_id
        self.ordering = ordering
