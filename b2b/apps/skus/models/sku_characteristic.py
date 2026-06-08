import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, IDMixin, TimestampMixin


class SKUCharacteristicValue(IDMixin, TimestampMixin, Base):
    __tablename__ = 'sku_characteristic_values'

    sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('skus.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(String(1024), nullable=False)

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        sku_id: uuid.UUID,
        name: str,
        value: str,
    ):
        if id is not None:
            self.id = id
        self.sku_id = sku_id
        self.name = name
        self.value = value
