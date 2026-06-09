import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, IDMixin, TimestampMixin


class Cart(IDMixin, TimestampMixin, Base):
    """Корзина покупателя.

    Одна из двух идентичностей задана:
    - `user_id` — для авторизованных (BUYER из JWT)
    - `session_id` — для гостей (X-Session-Id)

    После merge на /auth/login (US-ORD-01 / явный /cart/merge) гостевая корзина
    удаляется. В таблице соответственно либо user_id, либо session_id NOT NULL,
    но не оба сразу.
    """

    __tablename__ = 'carts'
    __table_args__ = (
        CheckConstraint(
            '(user_id IS NOT NULL) OR (session_id IS NOT NULL)',
            name='cart_identity_present',
        ),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('users.id'),
        index=True,
        unique=True,
        nullable=True,
    )
    session_id: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
        unique=True,
        nullable=True,
    )

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        session_id: str | None = None,
    ):
        if id is not None:
            self.id = id
        self.user_id = user_id
        self.session_id = session_id
