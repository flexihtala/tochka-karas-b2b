import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.products.enums import ProductStatus
from db import Base, IDMixin, TimestampMixin


class Product(IDMixin, TimestampMixin, Base):
    __tablename__ = 'products'

    seller_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProductStatus] = mapped_column(String(20), nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    category_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('categories.id'), nullable=False)
    images: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    characteristics: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list, server_default='[]')
