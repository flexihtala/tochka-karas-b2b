from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.subscriptions.errors import SubscriptionAlreadyExistsError, SubscriptionNotFoundError
from apps.subscriptions.schemas.db import SubscriptionReadSchema
from apps.subscriptions.schemas.request import SubscriptionCreateRequestSchema
from apps.subscriptions.use_cases import SubscribeUseCase, UnsubscribeUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.subscriptions.fakes import FakeSubscriptionRepository


def make_user() -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)


def make_subscription(user_id, product_id=None, notify_on=None) -> SubscriptionReadSchema:
    now = datetime.now(UTC)
    return SubscriptionReadSchema(
        id=uuid4(),
        user_id=user_id,
        product_id=product_id or uuid4(),
        notify_on=notify_on or ['PRICE_DROP', 'BACK_IN_STOCK'],
        created_at=now,
        updated_at=now,
    )


def create_request(product_id=None, notify_on=None) -> SubscriptionCreateRequestSchema:
    return SubscriptionCreateRequestSchema(
        product_id=product_id or uuid4(),
        notify_on=notify_on or ['PRICE_DROP', 'BACK_IN_STOCK'],
    )


@pytest.mark.anyio
async def test_subscribe_use_case_uses_jwt_user_id():
    user = make_user()
    repo = FakeSubscriptionRepository()
    use_case = SubscribeUseCase(subscription_repository=repo)

    request = create_request()
    result = await use_case(request, user)

    assert result.user_id == user.id
    assert repo.created[0].user_id == user.id
    assert repo.created[0].product_id == request.product_id
    assert repo.created[0].notify_on == request.notify_on


@pytest.mark.anyio
async def test_subscribe_use_case_returns_subscription_with_notify_on():
    user = make_user()
    repo = FakeSubscriptionRepository()
    use_case = SubscribeUseCase(subscription_repository=repo)

    request = create_request(notify_on=['PRICE_DROP'])
    result = await use_case(request, user)

    assert result.notify_on == ['PRICE_DROP']
    assert result.product_id == request.product_id


@pytest.mark.anyio
async def test_subscribe_use_case_raises_on_duplicate():
    user = make_user()
    product_id = uuid4()
    repo = FakeSubscriptionRepository()
    repo.add(make_subscription(user.id, product_id))

    use_case = SubscribeUseCase(subscription_repository=repo)

    with pytest.raises(SubscriptionAlreadyExistsError):
        await use_case(create_request(product_id=product_id), user)


@pytest.mark.anyio
async def test_subscribe_use_case_allows_same_product_for_different_users():
    user_a = make_user()
    user_b = make_user()
    product_id = uuid4()
    repo = FakeSubscriptionRepository()
    repo.add(make_subscription(user_a.id, product_id))

    use_case = SubscribeUseCase(subscription_repository=repo)
    result = await use_case(create_request(product_id=product_id), user_b)

    assert result.user_id == user_b.id
    assert result.product_id == product_id


@pytest.mark.anyio
async def test_subscribe_use_case_allows_same_user_different_products():
    user = make_user()
    repo = FakeSubscriptionRepository()
    repo.add(make_subscription(user.id))  # некая другая подписка

    use_case = SubscribeUseCase(subscription_repository=repo)
    new_product = uuid4()
    result = await use_case(create_request(product_id=new_product), user)

    assert result.product_id == new_product


@pytest.mark.anyio
async def test_unsubscribe_use_case_removes_subscription():
    user = make_user()
    product_id = uuid4()
    repo = FakeSubscriptionRepository()
    sub = make_subscription(user.id, product_id)
    repo.add(sub)

    use_case = UnsubscribeUseCase(subscription_repository=repo)
    await use_case(product_id, user)

    assert sub.id not in repo.by_id
    assert repo.deleted == [(user.id, product_id)]


@pytest.mark.anyio
async def test_unsubscribe_use_case_raises_when_subscription_missing():
    user = make_user()
    repo = FakeSubscriptionRepository()
    use_case = UnsubscribeUseCase(subscription_repository=repo)

    with pytest.raises(SubscriptionNotFoundError):
        await use_case(uuid4(), user)


@pytest.mark.anyio
async def test_unsubscribe_does_not_remove_other_users_subscription():
    user = make_user()
    other = make_user()
    product_id = uuid4()
    repo = FakeSubscriptionRepository()
    foreign = make_subscription(other.id, product_id)
    repo.add(foreign)

    use_case = UnsubscribeUseCase(subscription_repository=repo)

    with pytest.raises(SubscriptionNotFoundError):
        await use_case(product_id, user)

    assert foreign.id in repo.by_id
