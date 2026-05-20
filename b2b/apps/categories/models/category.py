import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, IDMixin, TimestampMixin


class Category(IDMixin, TimestampMixin, Base):
    __tablename__ = 'categories'

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('categories.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        name: str,
        parent_id: uuid.UUID | None = None,
    ):
        if id is not None:
            self.id = id
        self.name = name
        self.parent_id = parent_id
