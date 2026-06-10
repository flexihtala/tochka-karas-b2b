import uuid

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, IDMixin, TimestampMixin


class Favorite(IDMixin, TimestampMixin, Base):
    """Избранный товар покупателя.

    Хранит только связку (user_id, product_id) — продукт батч-обогащается из B2B
    при чтении списка. UNIQUE(user_id, product_id) обеспечивает идемпотентность
    добавления и защищает от дублей.
    """

    __tablename__ = 'favorites'
    __table_args__ = (UniqueConstraint('user_id', 'product_id', name='uq_favorites_user_product'),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
    ):
        if id is not None:
            self.id = id
        self.user_id = user_id
        self.product_id = product_id
