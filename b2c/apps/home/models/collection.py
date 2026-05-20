import uuid

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, IDMixin, TimestampMixin


class Collection(IDMixin, TimestampMixin, Base):
    """Подборка товаров на главной странице b2c.

    Бизнес-правила (US-CART-05):
    - Метаданные подборки хранятся в b2c, а сами товары — uuid-only в CollectionItem.
    - is_active=true → подборка попадает в выдачу `GET /home/collections`.
    - Сортировка списка: position ASC, затем created_at ASC.
    """

    __tablename__ = 'collections'

    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default='true')

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        slug: str,
        title: str,
        description: str | None = None,
        position: int = 0,
        is_active: bool = True,
    ):
        if id is not None:
            self.id = id
        self.slug = slug
        self.title = title
        self.description = description
        self.position = position
        self.is_active = is_active
