from uuid import UUID, uuid4

import pytest

from apps.invoices.enums import InvoiceStatus
from apps.invoices.errors import (
    InvoiceEmptyItemsError,
    InvoiceNotOwnerError,
    InvoiceSKUNotFoundError,
    InvoiceSKUNotModeratedError,
)
from apps.invoices.schemas.request import (
    InvoiceCreateRequestSchema,
    InvoiceItemCreateRequestSchema,
)
from apps.invoices.use_cases.create_invoice import CreateInvoiceUseCase
from apps.products.enums import ProductStatus
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.invoices.fakes import (
    FakeInvoiceItemRepository,
    FakeInvoiceRepository,
    FakeProductRepositoryReadable,
    FakeSKURepositoryReadable,
)


def make_authenticated_user(user_id: UUID | None = None, role: UserRole = UserRole.SELLER) -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=user_id or uuid4(), role=role)


def make_request(items: list[InvoiceItemCreateRequestSchema] | None = None) -> InvoiceCreateRequestSchema:
    if items is None:
        items = [InvoiceItemCreateRequestSchema(sku_id=uuid4(), quantity=10)]
    return InvoiceCreateRequestSchema(items=items)


def make_use_case(
    *,
    invoice_repository: FakeInvoiceRepository | None = None,
    invoice_item_repository: FakeInvoiceItemRepository | None = None,
    sku_repository: FakeSKURepositoryReadable | None = None,
    product_repository: FakeProductRepositoryReadable | None = None,
) -> CreateInvoiceUseCase:
    return CreateInvoiceUseCase(
        invoice_repository=invoice_repository or FakeInvoiceRepository(),
        invoice_item_repository=invoice_item_repository or FakeInvoiceItemRepository(),
        sku_repository=sku_repository or FakeSKURepositoryReadable(),
        product_repository=product_repository or FakeProductRepositoryReadable(),
    )


@pytest.mark.anyio
async def test_create_invoice_with_moderated_sku_returns_201():
    """Happy-path: накладная с одним MODERATED SKU создаётся со статусом CREATED."""
    user = make_authenticated_user()
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepositoryReadable()
    invoices = FakeInvoiceRepository()
    items_repo = FakeInvoiceItemRepository()

    product_id = products.add(seller_id=user.id, status=ProductStatus.MODERATED)
    sku_id = skus.add(product_id=product_id)

    use_case = make_use_case(
        invoice_repository=invoices,
        invoice_item_repository=items_repo,
        sku_repository=skus,
        product_repository=products,
    )

    response = await use_case(
        make_request([InvoiceItemCreateRequestSchema(sku_id=sku_id, quantity=10)]),
        user,
    )

    assert response.seller_id == user.id
    assert response.status == InvoiceStatus.CREATED
    assert len(response.items) == 1
    assert response.items[0].sku_id == sku_id
    assert response.items[0].quantity == 10
    assert response.items[0].accepted_quantity == 0
    # Invoice + item действительно записаны в репозитории.
    assert len(invoices.created) == 1
    assert invoices.created[0].seller_id == user.id
    assert invoices.created[0].status == InvoiceStatus.CREATED
    assert len(items_repo.created) == 1
    assert items_repo.created[0].sku_id == sku_id
    assert items_repo.created[0].invoice_id == response.id


@pytest.mark.anyio
async def test_empty_items_returns_400():
    """Пустой items → InvoiceEmptyItemsError (400 INVALID_REQUEST)."""
    user = make_authenticated_user()
    use_case = make_use_case()

    with pytest.raises(InvoiceEmptyItemsError) as exc_info:
        await use_case(make_request(items=[]), user)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == 'INVALID_REQUEST'


@pytest.mark.anyio
async def test_non_moderated_sku_returns_400():
    """SKU чьего товара не в статусе MODERATED → 400 INVALID_REQUEST."""
    user = make_authenticated_user()
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepositoryReadable()
    invoices = FakeInvoiceRepository()

    # Товар в статусе ON_MODERATION — ещё не одобрен.
    product_id = products.add(seller_id=user.id, status=ProductStatus.ON_MODERATION)
    sku_id = skus.add(product_id=product_id)

    use_case = make_use_case(
        invoice_repository=invoices,
        sku_repository=skus,
        product_repository=products,
    )

    with pytest.raises(InvoiceSKUNotModeratedError) as exc_info:
        await use_case(
            make_request([InvoiceItemCreateRequestSchema(sku_id=sku_id, quantity=5)]),
            user,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == 'INVALID_REQUEST'
    # Накладная не должна быть создана при ошибке валидации позиций.
    assert invoices.created == []


@pytest.mark.anyio
async def test_others_sku_returns_403():
    """SKU принадлежит другому seller'у → 403 NOT_OWNER (IDOR protection)."""
    user = make_authenticated_user()
    other_seller_id = uuid4()
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepositoryReadable()
    invoices = FakeInvoiceRepository()

    foreign_product_id = products.add(seller_id=other_seller_id, status=ProductStatus.MODERATED)
    foreign_sku_id = skus.add(product_id=foreign_product_id)

    use_case = make_use_case(
        invoice_repository=invoices,
        sku_repository=skus,
        product_repository=products,
    )

    with pytest.raises(InvoiceNotOwnerError) as exc_info:
        await use_case(
            make_request([InvoiceItemCreateRequestSchema(sku_id=foreign_sku_id, quantity=1)]),
            user,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == 'NOT_OWNER'
    assert invoices.created == []


@pytest.mark.anyio
async def test_unknown_sku_returns_400():
    """SKU не существует → InvoiceSKUNotFoundError (400)."""
    user = make_authenticated_user()
    use_case = make_use_case()

    with pytest.raises(InvoiceSKUNotFoundError) as exc_info:
        await use_case(
            make_request([InvoiceItemCreateRequestSchema(sku_id=uuid4(), quantity=1)]),
            user,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == 'INVALID_REQUEST'


@pytest.mark.anyio
async def test_mixed_items_fail_fast_no_invoice_created():
    """При нескольких items, если хотя бы один невалиден — накладная не создаётся."""
    user = make_authenticated_user()
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepositoryReadable()
    invoices = FakeInvoiceRepository()
    items_repo = FakeInvoiceItemRepository()

    # Валидный SKU.
    product_a = products.add(seller_id=user.id, status=ProductStatus.MODERATED)
    sku_a = skus.add(product_id=product_a)
    # Не-MODERATED SKU.
    product_b = products.add(seller_id=user.id, status=ProductStatus.HARD_BLOCKED)
    sku_b = skus.add(product_id=product_b)

    use_case = make_use_case(
        invoice_repository=invoices,
        invoice_item_repository=items_repo,
        sku_repository=skus,
        product_repository=products,
    )

    with pytest.raises(InvoiceSKUNotModeratedError):
        await use_case(
            make_request(
                [
                    InvoiceItemCreateRequestSchema(sku_id=sku_a, quantity=1),
                    InvoiceItemCreateRequestSchema(sku_id=sku_b, quantity=1),
                ]
            ),
            user,
        )

    assert invoices.created == []
    assert items_repo.created == []


@pytest.mark.anyio
async def test_multiple_valid_items_all_created():
    """Несколько валидных позиций — все попадают в накладную."""
    user = make_authenticated_user()
    products = FakeProductRepositoryReadable()
    skus = FakeSKURepositoryReadable()
    invoices = FakeInvoiceRepository()
    items_repo = FakeInvoiceItemRepository()

    product_id = products.add(seller_id=user.id, status=ProductStatus.MODERATED)
    sku_a = skus.add(product_id=product_id)
    sku_b = skus.add(product_id=product_id)

    use_case = make_use_case(
        invoice_repository=invoices,
        invoice_item_repository=items_repo,
        sku_repository=skus,
        product_repository=products,
    )

    response = await use_case(
        make_request(
            [
                InvoiceItemCreateRequestSchema(sku_id=sku_a, quantity=10),
                InvoiceItemCreateRequestSchema(sku_id=sku_b, quantity=5),
            ]
        ),
        user,
    )

    assert len(response.items) == 2
    assert {i.sku_id for i in response.items} == {sku_a, sku_b}
    assert {i.quantity for i in response.items} == {10, 5}
    assert len(items_repo.created) == 2
