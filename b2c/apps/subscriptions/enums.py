from enum import StrEnum


class NotifyOn(StrEnum):
    """События, на которые покупатель может подписаться.

    - PRICE_DROP — снижение цены товара.
    - BACK_IN_STOCK — товар снова в наличии.
    """

    PRICE_DROP = 'PRICE_DROP'
    BACK_IN_STOCK = 'BACK_IN_STOCK'
