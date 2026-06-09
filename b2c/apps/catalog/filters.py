"""Парсинг deepObject-фильтров каталога из raw query string.

FastAPI не умеет нативно разбирать `filter[category_id]=X` в вложенный dict,
поэтому парсим вручную из `request.query_params.multi_items()`.

Поддерживаемые ключи (style: deepObject, explode: true — b2c/openapi.yaml):
- filter[category_id]
- filter[price_min]
- filter[price_max]
- filter[seller_id]
- filter[attributes][<key>]  — динамические характеристики; повтор ключа даёт список.

Невалидные значения (например price_min не integer, category_id не uuid)
приводят к InvalidFilterError → 400.
"""

import re
from collections.abc import Iterable

from pydantic import ValidationError

from apps.catalog.errors import InvalidFilterError
from apps.catalog.schemas.request import CatalogFilterSchema

# filter[attributes][color] → ('attributes', 'color')
_ATTRIBUTES_KEY_RE = re.compile(r'^filter\[attributes\]\[(?P<attr>[^\[\]]+)\]$')
# filter[price_min] → ('price_min',)
_SCALAR_KEY_RE = re.compile(r'^filter\[(?P<field>category_id|price_min|price_max|seller_id)\]$')

_SCALAR_FIELDS = frozenset({'category_id', 'price_min', 'price_max', 'seller_id'})


def parse_deep_object_filter(query_params: Iterable[tuple[str, str]]) -> CatalogFilterSchema:
    """Собирает `CatalogFilterSchema` из пар (key, value) query string.

    Аргумент `query_params` — результат `request.query_params.multi_items()`
    (list[tuple[str, str]]), чтобы корректно обработать повторяющиеся ключи
    (несколько значений одного атрибута → список).
    """
    scalars: dict[str, str] = {}
    attributes: dict[str, list[str]] = {}

    for key, value in query_params:
        attr_match = _ATTRIBUTES_KEY_RE.match(key)
        if attr_match is not None:
            attr_name = attr_match.group('attr')
            attributes.setdefault(attr_name, []).append(value)
            continue

        scalar_match = _SCALAR_KEY_RE.match(key)
        if scalar_match is not None:
            scalars[scalar_match.group('field')] = value

    payload: dict[str, object] = dict(scalars)
    if attributes:
        # Одно значение → строка, несколько → список (как в spec oneOf[string, array]).
        payload['attributes'] = {
            name: values[0] if len(values) == 1 else values for name, values in attributes.items()
        }

    try:
        return CatalogFilterSchema.model_validate(payload)
    except ValidationError as exc:
        raise InvalidFilterError() from exc
