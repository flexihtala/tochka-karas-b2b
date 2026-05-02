from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from apps.auth.enums import UserRole
from apps.auth.errors import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenRevokedError,
)
from apps.auth.schemas.refresh_token import RefreshTokenCreateSchema
from apps.auth.schemas.request import (
    LoginRequestSchema,
    LogoutRequestSchema,
    RefreshRequestSchema,
    RegisterSellerRequestSchema,
)
from apps.auth.schemas.token import AuthenticatedUserSchema, JwtClaimsSchema
from apps.auth.use_cases.login import LoginUseCase
from apps.auth.use_cases.logout import LogoutUseCase
from apps.auth.use_cases.refresh import RefreshUseCase
from apps.auth.use_cases.register_seller import RegisterSellerUseCase
from settings import Settings
from tests.auth.fakes import (
    FakeJwtService,
    FakePasswordHasher,
    FakeRefreshBlacklistRepository,
    FakeRefreshTokenRepository,
    FakeUserRepository,
    make_user_read_schema,
)


def make_settings() -> Settings:
    return Settings(DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost/postgres')


def register_request(email: str = 'seller@example.com', inn: str = '7707083893') -> RegisterSellerRequestSchema:
    return RegisterSellerRequestSchema(
        email=email,
        password='SecurePass123!',
        company_name='OOO Primer',
        inn=inn,
        first_name='Ivan',
        last_name='Ivanov',
        phone='+79001234567',
    )


@pytest.mark.anyio
async def test_register_seller_creates_user_refresh_token_and_returns_tokens():
    users = FakeUserRepository()
    refresh_tokens = FakeRefreshTokenRepository()
    jwt_service = FakeJwtService()

    use_case = RegisterSellerUseCase(
        user_repository=users,
        refresh_token_repository=refresh_tokens,
        password_hasher=FakePasswordHasher(),
        jwt_service=jwt_service,
        settings=make_settings(),
    )

    result = await use_case(register_request())

    assert result.user_id in users.users_by_id
    assert result.access_token == 'access-1'
    assert result.refresh_token == 'refresh-1'
    assert result.expires_in == 3600
    assert users.created[0].password_hash == 'hashed:SecurePass123!'
    assert users.created[0].role == UserRole.SELLER
    assert refresh_tokens.created[0].user_id == result.user_id
    assert refresh_tokens.created[0].jti == jwt_service.issued_pairs[0].refresh.claims.jti


@pytest.mark.anyio
async def test_register_seller_rejects_duplicate_email():
    users = FakeUserRepository()
    users.add(make_user_read_schema(email='seller@example.com'))

    use_case = RegisterSellerUseCase(
        user_repository=users,
        refresh_token_repository=FakeRefreshTokenRepository(),
        password_hasher=FakePasswordHasher(),
        jwt_service=FakeJwtService(),
        settings=make_settings(),
    )

    with pytest.raises(EmailAlreadyExistsError):
        await use_case(register_request())


@pytest.mark.anyio
async def test_login_returns_tokens_for_valid_credentials():
    users = FakeUserRepository()
    user = make_user_read_schema(email='seller@example.com', password_hash='hashed:SecurePass123!')
    users.add(user)
    refresh_tokens = FakeRefreshTokenRepository()

    use_case = LoginUseCase(
        user_repository=users,
        refresh_token_repository=refresh_tokens,
        password_hasher=FakePasswordHasher(),
        jwt_service=FakeJwtService(),
        settings=make_settings(),
    )

    result = await use_case(LoginRequestSchema(email='seller@example.com', password='SecurePass123!'))

    assert result.user_id == user.id
    assert result.access_token == 'access-1'
    assert refresh_tokens.created[0].user_id == user.id


@pytest.mark.anyio
async def test_login_rejects_invalid_password():
    users = FakeUserRepository()
    users.add(make_user_read_schema(email='seller@example.com', password_hash='hashed:SecurePass123!'))

    use_case = LoginUseCase(
        user_repository=users,
        refresh_token_repository=FakeRefreshTokenRepository(),
        password_hasher=FakePasswordHasher(),
        jwt_service=FakeJwtService(),
        settings=make_settings(),
    )

    with pytest.raises(InvalidCredentialsError):
        await use_case(LoginRequestSchema(email='seller@example.com', password='WrongPass123!'))


@pytest.mark.anyio
async def test_refresh_rotates_refresh_token():
    users = FakeUserRepository()
    user = make_user_read_schema()
    users.add(user)

    old_jti = uuid4()
    now = datetime.now(UTC)
    claims = JwtClaimsSchema(
        sub=user.id,
        role=user.role,
        iat=int(now.timestamp()),
        exp=int((now + timedelta(days=30)).timestamp()),
        jti=old_jti,
    )
    jwt_service = FakeJwtService()
    jwt_service.set_decoded('old-refresh', claims)

    refresh_tokens = FakeRefreshTokenRepository()
    await refresh_tokens.create(
        RefreshTokenCreateSchema(
            jti=old_jti,
            user_id=user.id,
            issued_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    blacklist = FakeRefreshBlacklistRepository()

    use_case = RefreshUseCase(
        user_repository=users,
        refresh_token_repository=refresh_tokens,
        refresh_blacklist_repository=blacklist,
        jwt_service=jwt_service,
        settings=make_settings(),
    )

    result = await use_case(RefreshRequestSchema(refresh_token='old-refresh'))

    assert result.access_token == 'access-1'
    assert result.refresh_token == 'refresh-1'
    assert old_jti in blacklist.jtis
    assert old_jti in refresh_tokens.deleted
    assert jwt_service.issued_pairs[0].refresh.claims.jti in refresh_tokens.tokens


@pytest.mark.anyio
async def test_refresh_rejects_revoked_token():
    old_jti = uuid4()
    jwt_service = FakeJwtService()
    jwt_service.set_decoded(
        'old-refresh',
        JwtClaimsSchema(
            sub=uuid4(),
            role=UserRole.SELLER,
            iat=1,
            exp=2,
            jti=old_jti,
        ),
    )
    blacklist = FakeRefreshBlacklistRepository()
    blacklist.jtis.add(old_jti)

    use_case = RefreshUseCase(
        user_repository=FakeUserRepository(),
        refresh_token_repository=FakeRefreshTokenRepository(),
        refresh_blacklist_repository=blacklist,
        jwt_service=jwt_service,
        settings=make_settings(),
    )

    with pytest.raises(TokenRevokedError):
        await use_case(RefreshRequestSchema(refresh_token='old-refresh'))


@pytest.mark.anyio
async def test_logout_blacklists_refresh_token_for_current_user():
    user_id = uuid4()
    jti = uuid4()
    jwt_service = FakeJwtService()
    jwt_service.set_decoded(
        'refresh-token',
        JwtClaimsSchema(
            sub=user_id,
            role=UserRole.SELLER,
            iat=1,
            exp=int((datetime.now(UTC) + timedelta(days=30)).timestamp()),
            jti=jti,
        ),
    )
    blacklist = FakeRefreshBlacklistRepository()

    use_case = LogoutUseCase(refresh_blacklist_repository=blacklist, jwt_service=jwt_service)

    await use_case(
        LogoutRequestSchema(refresh_token='refresh-token'),
        AuthenticatedUserSchema(id=user_id, role=UserRole.SELLER),
    )

    assert jti in blacklist.jtis


@pytest.mark.anyio
async def test_logout_rejects_refresh_token_from_another_user():
    jwt_service = FakeJwtService()
    jwt_service.set_decoded(
        'refresh-token',
        JwtClaimsSchema(
            sub=uuid4(),
            role=UserRole.SELLER,
            iat=1,
            exp=2,
            jti=uuid4(),
        ),
    )
    use_case = LogoutUseCase(
        refresh_blacklist_repository=FakeRefreshBlacklistRepository(),
        jwt_service=jwt_service,
    )

    with pytest.raises(InvalidTokenError):
        await use_case(
            LogoutRequestSchema(refresh_token='refresh-token'),
            AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER),
        )
