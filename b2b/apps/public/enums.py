from enum import StrEnum


class CatalogSort(StrEnum):
    """Варианты сортировки витрины (см. OpenAPI listPublicProducts.sort).

    - PRICE_ASC / PRICE_DESC — по минимальной цене SKU товара.
    - CREATED_DESC — по дате создания товара (новые первыми), значение по умолчанию.
    - POPULAR — популярность. MVP: эвристика отсутствует, поэтому деградирует
      до CREATED_DESC (документировано; см. repositories/catalog_repository.py).
    """

    PRICE_ASC = 'price_asc'
    PRICE_DESC = 'price_desc'
    CREATED_DESC = 'created_desc'
    POPULAR = 'popular'
