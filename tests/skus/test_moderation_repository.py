from uuid import UUID, uuid4

import pytest

from apps.skus.repositories import ModerationRepository
from apps.skus.schemas.moderation import ProductModerationEventSchema
from settings import Settings


@pytest.mark.anyio
async def test_moderation_repository_sends_product_created_event(httpx_mock):
    service_key = str(uuid4())
    settings = Settings(
        DATABASE_URL='postgresql+asyncpg://postgres@localhost/postgres',
        MODERATION_URL='https://moderation.example.test',
        B2B_TO_MOD_KEY=service_key,
    )
    httpx_mock.add_response(method='POST', url='https://moderation.example.test/api/v1/events/product')

    await ModerationRepository(settings).send_product_event(
        ProductModerationEventSchema(
            idempotency_key=uuid4(),
            product_id=uuid4(),
            seller_id=uuid4(),
            event='CREATED',
            date='2026-03-15T14:30:00.000Z',
        )
    )

    request = httpx_mock.get_request()
    assert request is not None
    assert request.headers['X-Service-Key'] == service_key
    body = request.read()
    assert b'"event":"CREATED"' in body
    assert UUID(request.headers['X-Service-Key'])
