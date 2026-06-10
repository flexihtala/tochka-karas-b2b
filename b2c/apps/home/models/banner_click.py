import uuid

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, IDMixin, TimestampMixin


class BannerClick(IDMixin, TimestampMixin, Base):
    """Событие клика по баннеру.

    Бизнес-правила (US-CART-04):
    - user_id nullable — анонимные пользователи тоже могут кликать.
    - banner_id FK на banners.id; клик по несуществующему баннеру → 400.
    - Reads (агрегация CTR) — out of scope этого квеста, см. ADR.

    Поле updated_at от TimestampMixin не несёт смысла для immutable события,
    но оставлено ради унифицированной структуры таблиц.
    """

    __tablename__ = 'banner_clicks'

    banner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('banners.id'),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True, nullable=True)

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        banner_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ):
        if id is not None:
            self.id = id
        self.banner_id = banner_id
        self.user_id = user_id
