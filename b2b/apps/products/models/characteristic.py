import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, IDMixin, TimestampMixin


class CharacteristicValue(IDMixin, TimestampMixin, Base):
    __tablename__ = 'characteristic_values'

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('products.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(String(1024), nullable=False)

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        product_id: uuid.UUID,
        name: str,
        value: str,
    ):
        if id is not None:
            self.id = id
        self.product_id = product_id
        self.name = name
        self.value = value
