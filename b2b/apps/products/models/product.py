import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.products.enums import ProductStatus
from db import Base, IDMixin, TimestampMixin


class Product(IDMixin, TimestampMixin, Base):
    __tablename__ = 'products'

    seller_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('users.id'),
        index=True,
        nullable=False,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('categories.id'),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProductStatus] = mapped_column(
        String(32),
        nullable=False,
        default=ProductStatus.CREATED,
        server_default=ProductStatus.CREATED.value,
    )
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    blocking_reason_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    blocking_reason_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    moderator_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_reports: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default='[]',
    )

    images: Mapped[list['ProductImage']] = relationship(  # noqa: F821
        'ProductImage',
        cascade='all, delete-orphan',
        lazy='selectin',
        order_by='ProductImage.ordering',
    )
    characteristics: Mapped[list['CharacteristicValue']] = relationship(  # noqa: F821
        'CharacteristicValue',
        cascade='all, delete-orphan',
        lazy='selectin',
    )

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        seller_id: uuid.UUID,
        category_id: uuid.UUID,
        title: str,
        slug: str,
        description: str,
        status: ProductStatus = ProductStatus.CREATED,
        deleted: bool = False,
        blocking_reason_id: uuid.UUID | None = None,
        blocking_reason_title: str | None = None,
        moderator_comment: str | None = None,
        field_reports: list[dict[str, Any]] | None = None,
    ):
        if id is not None:
            self.id = id
        self.seller_id = seller_id
        self.category_id = category_id
        self.title = title
        self.slug = slug
        self.description = description
        self.status = status
        self.deleted = deleted
        self.blocking_reason_id = blocking_reason_id
        self.blocking_reason_title = blocking_reason_title
        self.moderator_comment = moderator_comment
        self.field_reports = field_reports if field_reports is not None else []
