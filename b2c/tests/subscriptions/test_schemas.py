from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.subscriptions.enums import NotifyOn
from apps.subscriptions.schemas.request import SubscriptionCreateRequestSchema


def test_notify_on_enum_contains_protocol_values():
    """Гарантируем что enum NotifyOn содержит значения из протокола."""
    assert NotifyOn.PRICE_DROP.value == 'PRICE_DROP'
    assert NotifyOn.BACK_IN_STOCK.value == 'BACK_IN_STOCK'


def test_request_schema_accepts_valid_notify_on():
    schema = SubscriptionCreateRequestSchema(
        product_id=uuid4(),
        notify_on=['PRICE_DROP', 'BACK_IN_STOCK'],
    )
    assert schema.notify_on == ['PRICE_DROP', 'BACK_IN_STOCK']


def test_request_schema_rejects_invalid_notify_on_value():
    with pytest.raises(ValidationError):
        SubscriptionCreateRequestSchema(product_id=uuid4(), notify_on=['HEY_HO'])


def test_request_schema_rejects_empty_notify_on():
    with pytest.raises(ValidationError):
        SubscriptionCreateRequestSchema(product_id=uuid4(), notify_on=[])


def test_request_schema_dedupes_notify_on():
    schema = SubscriptionCreateRequestSchema(
        product_id=uuid4(),
        notify_on=['PRICE_DROP', 'PRICE_DROP', 'BACK_IN_STOCK'],
    )
    assert schema.notify_on == ['PRICE_DROP', 'BACK_IN_STOCK']
