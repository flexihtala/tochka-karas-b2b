import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, IDMixin, TimestampMixin


class Banner(IDMixin, TimestampMixin, Base):
    """Промо-баннер главной страницы b2c.

    Бизнес-правила (US-CART-04):
    - is_active=true И (schedule_start IS NULL ИЛИ schedule_start <= now)
                    И (schedule_end   IS NULL ИЛИ schedule_end   >= now)
      → баннер активен.
    - Сортировка выдачи: priority DESC (большее число — выше).
    - CRUD-управление — отдельный домен (Django-Admin), здесь не реализуется.
    """

    __tablename__ = 'banners'

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    image_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    link_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default='true')
    schedule_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    schedule_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        title: str,
        image_url: str,
        link_url: str,
        priority: int = 0,
        is_active: bool = True,
        schedule_start: datetime | None = None,
        schedule_end: datetime | None = None,
    ):
        if id is not None:
            self.id = id
        self.title = title
        self.image_url = image_url
        self.link_url = link_url
        self.priority = priority
        self.is_active = is_active
        self.schedule_start = schedule_start
        self.schedule_end = schedule_end
