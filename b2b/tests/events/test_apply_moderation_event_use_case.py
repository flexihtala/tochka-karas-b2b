"""US-B2B-09 — обработка входящих событий от Moderation.

Покрытие (Definition of Done):
- test_moderated_event_clears_blocking_data — MODERATED → status=MODERATED + очистка blocking_*.
- test_blocked_soft_saves_field_reports — BLOCKED soft → status=BLOCKED + reason/comment/field_reports + outbox B2C.
- test_blocked_hard_sets_terminal_status — BLOCKED hard → status=HARD_BLOCKED (терминальный) + outbox B2C.
- test_hard_blocked_product_rejects_seller_edits — HARD_BLOCKED товар: seller PATCH/DELETE → 403.
- test_duplicate_event_same_idempotency_key_no_side_effects — повтор idempotency_key → cached, без side-effects.

Доп. покрытие: BLOCKED без reason → 400, product_id не найден → 404.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from apps.events.errors import BlockedReasonRequiredError, EventProductNotFoundError
from apps.events.schemas.request import (
    FieldReportSchema,
    ModerationEventRequestSchema,
    ModerationEventType,
)
from apps.events.use_cases.apply_moderation_event import ApplyModerationEventUseCase
from apps.products.enums import ProductStatus
from apps.products.errors import ProductHardBlockedError
from apps.products.schemas.request import ProductEditRequestSchema
from apps.products.use_cases.delete_product import DeleteProductUseCase
from apps.products.use_cases.edit_product import EditProductUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from shared.types import ServiceName
from tests.events.fakes import (
    FakeIdempotentHandler,
    FakeOutboxRepositoryForEvents,
    FakeProductRepositoryForEvents,
    FakeSessionManager,
    FakeSKURepositoryForEvents,
)
from tests.products.fakes import (
    FakeCategoryRepository,
    FakeCharacteristicValueRepository,
    FakeOutboxRepository,
    FakeProductImageRepository,
    FakeProductRepository,
    FakeSKUCharacteristicValueRepository,
    FakeSKUImageRepository,
    FakeSKURepositoryForDelete,
    FakeSKURepositoryForProducts,
)


def make_use_case(
    *,
    product_repository: FakeProductRepositoryForEvents | None = None,
    sku_repository: FakeSKURepositoryForEvents | None = None,
    outbox_repository: FakeOutboxRepositoryForEvents | None = None,
    idempotent_handler: FakeIdempotentHandler | None = None,
) -> ApplyModerationEventUseCase:
    return ApplyModerationEventUseCase(
        session_manager=FakeSessionManager(),  # type: ignore[arg-type]
        idempotent_handler=idempotent_handler or FakeIdempotentHandler(),  # type: ignore[arg-type]
        product_repository=product_repository or FakeProductRepositoryForEvents(),  # type: ignore[arg-type]
        sku_repository=sku_repository or FakeSKURepositoryForEvents(),  # type: ignore[arg-type]
        outbox_repository=outbox_repository or FakeOutboxRepositoryForEvents(),  # type: ignore[arg-type]
    )


def make_moderated_event(*, product_id: UUID, idempotency_key: UUID | None = None) -> ModerationEventRequestSchema:
    return ModerationEventRequestSchema(
        idempotency_key=idempotency_key or uuid4(),
        product_id=product_id,
        event_type=ModerationEventType.MODERATED,
        occurred_at=datetime.now(UTC),
    )


def make_blocked_event(
    *,
    product_id: UUID,
    hard_block: bool = False,
    blocking_reason_id: UUID | None = None,
    moderator_comment: str | None = 'Несоответствие описания и фотографий',
    field_reports: list[FieldReportSchema] | None = None,
    idempotency_key: UUID | None = None,
) -> ModerationEventRequestSchema:
    return ModerationEventRequestSchema(
        idempotency_key=idempotency_key or uuid4(),
        product_id=product_id,
        event_type=ModerationEventType.BLOCKED,
        blocking_reason_id=blocking_reason_id or uuid4(),
        moderator_comment=moderator_comment,
        hard_block=hard_block,
        field_reports=field_reports,
        occurred_at=datetime.now(UTC),
    )


@pytest.mark.anyio
async def test_moderated_event_clears_blocking_data():
    """MODERATED event → status MODERATED + blocking_*/field_reports очищены."""
    products = FakeProductRepositoryForEvents()
    # Товар был ранее заблокирован.
    product_id = products.add(
        status=ProductStatus.BLOCKED,
        blocking_reason_id=uuid4(),
        moderator_comment='старый коммент',
        field_reports=[{'field_name': 'description', 'sku_id': None, 'comment': 'old'}],
    )
    outbox = FakeOutboxRepositoryForEvents()
    use_case = make_use_case(product_repository=products, outbox_repository=outbox)

    response = await use_case(make_moderated_event(product_id=product_id))

    assert response.product_id == product_id
    assert response.status == ProductStatus.MODERATED

    updated_product = products.by_id[product_id]
    assert updated_product.status == ProductStatus.MODERATED
    assert updated_product.blocking_reason_id is None
    assert updated_product.moderator_comment is None
    # field_reports NOT NULL: «очищено» = пустой список, а не None.
    assert updated_product.field_reports == []

    # На MODERATED — никаких каскадных событий в B2C.
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_blocked_soft_saves_field_reports():
    """BLOCKED soft → status BLOCKED + сохранены reason/comment/field_reports + outbox для B2C."""
    products = FakeProductRepositoryForEvents()
    skus = FakeSKURepositoryForEvents()
    outbox = FakeOutboxRepositoryForEvents()

    product_id = products.add(status=ProductStatus.ON_MODERATION)
    sku_ids = [uuid4(), uuid4()]
    skus.add(product_id, sku_ids)

    reason_id = uuid4()
    field_reports = [
        FieldReportSchema(field_name='description', sku_id=None, comment='Скопировано'),
        FieldReportSchema(field_name='images[0]', sku_id=sku_ids[0], comment='Фото не товара'),
    ]

    use_case = make_use_case(product_repository=products, sku_repository=skus, outbox_repository=outbox)

    response = await use_case(
        make_blocked_event(
            product_id=product_id,
            hard_block=False,
            blocking_reason_id=reason_id,
            moderator_comment='Несоответствие описания и фото',
            field_reports=field_reports,
        )
    )

    assert response.status == ProductStatus.BLOCKED

    updated_product = products.by_id[product_id]
    assert updated_product.status == ProductStatus.BLOCKED
    assert updated_product.blocking_reason_id == reason_id
    assert updated_product.moderator_comment == 'Несоответствие описания и фото'
    assert updated_product.field_reports is not None
    assert len(updated_product.field_reports) == 2
    field_names = {fr['field_name'] for fr in updated_product.field_reports}
    assert field_names == {'description', 'images[0]'}
    # sku_id сериализован в строку (JSON-совместимо).
    image_report = next(fr for fr in updated_product.field_reports if fr['field_name'] == 'images[0]')
    assert image_report['sku_id'] == str(sku_ids[0])
    # description-report не имеет sku_id.
    desc_report = next(fr for fr in updated_product.field_reports if fr['field_name'] == 'description')
    assert desc_report['sku_id'] is None

    # Каскадное событие в B2C.
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == 'PRODUCT_BLOCKED'
    assert event.target_service == ServiceName.B2C
    assert event.payload['product_id'] == str(product_id)
    assert set(event.payload['sku_ids']) == {str(sid) for sid in sku_ids}


@pytest.mark.anyio
async def test_blocked_hard_sets_terminal_status():
    """BLOCKED hard → status HARD_BLOCKED + сохранены blocking_* + outbox в B2C."""
    products = FakeProductRepositoryForEvents()
    skus = FakeSKURepositoryForEvents()
    outbox = FakeOutboxRepositoryForEvents()

    product_id = products.add(status=ProductStatus.ON_MODERATION)
    skus.add(product_id, [uuid4()])

    reason_id = uuid4()
    use_case = make_use_case(product_repository=products, sku_repository=skus, outbox_repository=outbox)

    response = await use_case(
        make_blocked_event(product_id=product_id, hard_block=True, blocking_reason_id=reason_id),
    )

    assert response.status == ProductStatus.HARD_BLOCKED

    updated_product = products.by_id[product_id]
    assert updated_product.status == ProductStatus.HARD_BLOCKED
    assert updated_product.blocking_reason_id == reason_id

    # Каскад в B2C даже при hard.
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == 'PRODUCT_BLOCKED'
    assert event.target_service == ServiceName.B2C


@pytest.mark.anyio
async def test_hard_blocked_product_rejects_seller_edits():
    """HARD_BLOCKED — терминальный статус: seller PATCH/DELETE запрещены (403).

    Сначала событие BLOCKED+hard_block переводит товар в HARD_BLOCKED. Затем
    тот же товар (с тем же seller_id) подаётся в seller-use-case'ы редактирования
    и удаления — оба должны бросить ProductHardBlockedError (403). Это доказывает,
    что терминальный guard в US-B2B-03/04 опирается ровно на статус, который
    выставляет US-B2B-09.
    """
    seller = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)

    # 1. Moderation hard-blocks the product (US-B2B-09).
    events_products = FakeProductRepositoryForEvents()
    product_id = events_products.add(seller_id=seller.id, status=ProductStatus.BLOCKED)
    apply_use_case = make_use_case(product_repository=events_products)

    await apply_use_case(make_blocked_event(product_id=product_id, hard_block=True))
    assert events_products.by_id[product_id].status == ProductStatus.HARD_BLOCKED

    # 2. Seller tries to PATCH the HARD_BLOCKED product → 403 (US-B2B-03).
    edit_products = FakeProductRepository()
    edit_products.add(id=product_id, seller_id=seller.id, status=ProductStatus.HARD_BLOCKED)
    edit_use_case = EditProductUseCase(
        product_repository=edit_products,  # type: ignore[arg-type]
        image_repository=FakeProductImageRepository(),  # type: ignore[arg-type]
        characteristic_repository=FakeCharacteristicValueRepository(),  # type: ignore[arg-type]
        category_repository=FakeCategoryRepository(),  # type: ignore[arg-type]
        sku_repository=FakeSKURepositoryForProducts(),  # type: ignore[arg-type]
        sku_image_repository=FakeSKUImageRepository(),  # type: ignore[arg-type]
        sku_characteristic_repository=FakeSKUCharacteristicValueRepository(),  # type: ignore[arg-type]
        outbox_repository=FakeOutboxRepository(),  # type: ignore[arg-type]
    )

    with pytest.raises(ProductHardBlockedError) as edit_exc:
        await edit_use_case(product_id, ProductEditRequestSchema(title='Новый заголовок'), seller)
    assert edit_exc.value.status_code == 403
    assert edit_exc.value.code == 'HARD_BLOCKED'

    # 3. Seller tries to DELETE the HARD_BLOCKED product → 403 (US-B2B-04).
    delete_products = FakeProductRepository()
    delete_products.add(id=product_id, seller_id=seller.id, status=ProductStatus.HARD_BLOCKED)
    delete_use_case = DeleteProductUseCase(
        product_repository=delete_products,  # type: ignore[arg-type]
        sku_repository=FakeSKURepositoryForDelete(),  # type: ignore[arg-type]
        outbox_repository=FakeOutboxRepository(),  # type: ignore[arg-type]
    )

    with pytest.raises(ProductHardBlockedError) as delete_exc:
        await delete_use_case(product_id, seller)
    assert delete_exc.value.status_code == 403
    assert delete_exc.value.code == 'HARD_BLOCKED'


@pytest.mark.anyio
async def test_duplicate_event_same_idempotency_key_no_side_effects():
    """Повторный POST с тем же idempotency_key:
    - handler НЕ вызывается повторно;
    - product НЕ обновляется второй раз;
    - outbox НЕ получает повторных событий;
    - возвращается тот же cached-ответ.
    """
    products = FakeProductRepositoryForEvents()
    skus = FakeSKURepositoryForEvents()
    outbox = FakeOutboxRepositoryForEvents()
    handler = FakeIdempotentHandler()

    product_id = products.add(status=ProductStatus.ON_MODERATION)
    skus.add(product_id, [uuid4()])

    use_case = make_use_case(
        product_repository=products,
        sku_repository=skus,
        outbox_repository=outbox,
        idempotent_handler=handler,
    )

    idempotency_key = uuid4()
    event = make_blocked_event(product_id=product_id, idempotency_key=idempotency_key)

    # 1-й вызов — handler выполняется, side-effects происходят.
    first_response = await use_case(event)
    assert handler.handler_invocations == 1
    assert len(products.updated) == 1
    assert len(outbox.enqueued) == 1

    # 2-й вызов с тем же idempotency_key — handler НЕ вызывается, side-effects не повторяются.
    second_response = await use_case(event)
    assert handler.handler_invocations == 1  # не выросло
    assert len(products.updated) == 1  # повторного update не было
    assert len(outbox.enqueued) == 1  # повторного outbox не было

    # Cached-ответ совпадает с первым.
    assert second_response.product_id == first_response.product_id
    assert second_response.status == first_response.status

    # Handler фиксирует оба обращения (для аудита/телеметрии),
    # но реальный business-handler выполнен только один раз.
    assert handler.calls == [(ServiceName.MODERATION, idempotency_key), (ServiceName.MODERATION, idempotency_key)]


@pytest.mark.anyio
async def test_blocked_without_reason_returns_400():
    """BLOCKED без blocking_reason_id → BlockedReasonRequiredError (400)."""
    products = FakeProductRepositoryForEvents()
    product_id = products.add()
    use_case = make_use_case(product_repository=products)

    # Schema позволяет blocking_reason_id=None, но use-case требует его при BLOCKED.
    event = ModerationEventRequestSchema(
        idempotency_key=uuid4(),
        product_id=product_id,
        event_type=ModerationEventType.BLOCKED,
        blocking_reason_id=None,
        hard_block=False,
        occurred_at=datetime.now(UTC),
    )

    with pytest.raises(BlockedReasonRequiredError) as exc_info:
        await use_case(event)
    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_product_not_found_returns_404():
    """product_id не существует → EventProductNotFoundError (404)."""
    use_case = make_use_case()

    with pytest.raises(EventProductNotFoundError) as exc_info:
        await use_case(make_moderated_event(product_id=uuid4()))
    assert exc_info.value.status_code == 404
