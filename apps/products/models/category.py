from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from db import Base, IDMixin


class Category(IDMixin, Base):
    __tablename__ = 'categories'

    name: Mapped[str] = mapped_column(String(255), nullable=False)
