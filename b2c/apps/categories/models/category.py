import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, IDMixin, TimestampMixin


class Category(IDMixin, TimestampMixin, Base):
    """Дерево категорий B2C — adjacency-list.

    Поля копируются из B2B (категории — seed-данные, меняются редко).
    parent_id указывает на родителя; NULL для корневых категорий.
    `ondelete='SET NULL'` страхует от случайного удаления родителя (orphan-node),
    но в нормальном цикле жизни дерева мы такого не ждём.
    """

    __tablename__ = 'categories'

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('categories.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    ordering: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        name: str,
        slug: str,
        parent_id: uuid.UUID | None = None,
        ordering: int = 0,
    ):
        if id is not None:
            self.id = id
        self.name = name
        self.slug = slug
        self.parent_id = parent_id
        self.ordering = ordering
