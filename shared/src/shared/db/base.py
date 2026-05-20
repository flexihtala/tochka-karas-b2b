from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый класс SQLAlchemy-моделей.

    Каждый сервис может либо использовать его напрямую, либо унаследовать
    свой собственный Base — но удобнее делить один на сервис, чтобы все
    модели регистрировались в одном MetaData (alembic autogenerate видит все).
    """
