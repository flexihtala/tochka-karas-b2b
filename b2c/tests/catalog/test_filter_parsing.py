"""Юнит-тесты deepObject-парсера фильтров каталога.

Парсер `parse_deep_object_filter` собирает `CatalogFilterSchema` из пар
(key, value) raw query string (`request.query_params.multi_items()`).
"""

from uuid import uuid4

import pytest

from apps.catalog.errors import InvalidFilterError
from apps.catalog.filters import parse_deep_object_filter


def test_deep_object_filter_parsed():
    """category_id + повторяющийся attributes-ключ → dict со списком значений."""
    category_id = uuid4()
    items = [
        ('filter[category_id]', str(category_id)),
        ('filter[attributes][color]', 'red'),
        ('filter[attributes][color]', 'blue'),
    ]

    result = parse_deep_object_filter(items)

    assert result.category_id == category_id
    assert result.attributes == {'color': ['red', 'blue']}


def test_single_attribute_value_is_string():
    """Одно значение атрибута → строка (а не список из одного элемента)."""
    result = parse_deep_object_filter([('filter[attributes][size]', 'M')])

    assert result.attributes == {'size': 'M'}


def test_all_scalar_filters_parsed():
    category_id = uuid4()
    seller_id = uuid4()
    items = [
        ('filter[category_id]', str(category_id)),
        ('filter[price_min]', '10000'),
        ('filter[price_max]', '50000'),
        ('filter[seller_id]', str(seller_id)),
    ]

    result = parse_deep_object_filter(items)

    assert result.category_id == category_id
    assert result.price_min == 10000
    assert result.price_max == 50000
    assert result.seller_id == seller_id
    assert result.attributes == {}


def test_empty_query_yields_empty_filter():
    result = parse_deep_object_filter([])

    assert result.is_empty()


def test_non_filter_keys_ignored():
    """q/sort/limit/offset и любые не-filter ключи парсер игнорирует."""
    result = parse_deep_object_filter(
        [
            ('q', 'phone'),
            ('sort', 'new'),
            ('limit', '20'),
            ('offset', '0'),
            ('category_id', str(uuid4())),  # плоский (без filter[...]) — игнор
        ]
    )

    assert result.is_empty()


def test_multiple_distinct_attributes():
    result = parse_deep_object_filter(
        [
            ('filter[attributes][color]', 'red'),
            ('filter[attributes][size]', 'XL'),
        ]
    )

    assert result.attributes == {'color': 'red', 'size': 'XL'}


def test_invalid_price_raises_invalid_filter_error():
    with pytest.raises(InvalidFilterError):
        parse_deep_object_filter([('filter[price_min]', 'not-a-number')])


def test_negative_price_raises_invalid_filter_error():
    with pytest.raises(InvalidFilterError):
        parse_deep_object_filter([('filter[price_min]', '-1')])


def test_invalid_uuid_raises_invalid_filter_error():
    with pytest.raises(InvalidFilterError):
        parse_deep_object_filter([('filter[category_id]', 'not-a-uuid')])
