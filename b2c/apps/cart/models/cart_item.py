import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, IDMixin, TimestampMixin


class CartItem(IDMixin, TimestampMixin, Base):
    """Позиция корзины — ссылка на SKU из B2B + quantity.

    B2C не хранит ни цену, ни название — всё это динамически обогащается из B2B
    при GET /api/v1/cart (см. b2c-cart-flows.md, Flow B2C-8).

    UNIQUE(cart_id, sku_id) — один SKU не может быть в корзине дважды;
    add-to-cart инкрементирует quantity при повторном добавлении.
    """

    __tablename__ = 'cart_items'
    __table_args__ = (
        CheckConstraint('quantity >= 1', name='cart_item_quantity_positive'),
        UniqueConstraint('cart_id', 'sku_id', name='uq_cart_items_cart_sku'),
    )

    cart_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('carts.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        cart_id: uuid.UUID,
        sku_id: uuid.UUID,
        product_id: uuid.UUID | None = None,
        quantity: int,
    ):
        if id is not None:
            self.id = id
        self.cart_id = cart_id
        self.sku_id = sku_id
        self.product_id = product_id
        self.quantity = quantity
