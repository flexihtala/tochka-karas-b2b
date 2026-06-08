"""Repository для работы с профилем покупателя.

В b2c есть единая таблица users — все её записи это buyers (role=BUYER).
Этот repository — фасад над UserRepository для buyers-домена.
"""

from apps.auth.repositories import UserRepository as _UserRepository


class BuyerRepository(_UserRepository):
    """Алиас UserRepository в buyers-домене — оставлен отдельным классом
    для DI/типизации и чтобы будущие изменения не ломали auth.
    """
