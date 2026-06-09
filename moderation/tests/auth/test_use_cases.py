from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from apps.auth.errors import (
    InvalidCredentialsError,
    InvalidTokenError,
    TokenRevokedError,
    UserBlockedError,
)
from apps.auth.schemas.refresh_token import RefreshTokenCreateSchema
from apps.auth.schemas.request import LoginRequestSchema, LogoutRequestSchema, RefreshRequestSchema
from apps.auth.use_cases.login import LoginUseCase
from apps.auth.use_cases.logout import LogoutUseCase
from apps.auth.use_cases.refresh import RefreshUseCase
from settings import ModerationSettings
from shared.auth_lib import AuthenticatedUserSchema, JwtClaimsSchema, UserRole
from tests.auth.fakes import (
    FakeJwtService,
    FakeModeratorRepository,
    FakePasswordHasher,
    FakeRefreshBlacklistRepository,
    FakeRefreshTokenRepository,
    make_moderator_read_schema,
)


def make_settings() -> ModerationSettings:
    return ModerationSettings(DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost/postgres')


@pytest.mark.anyio
async def test_login_returns_tokens_for_valid_credentials():
    moderators = FakeModeratorRepository()
    moderator = make_moderator_read_schema(email='mod@example.com', password_hash='hashed:SecurePass123!')
    moderators.add(moderator)
    refresh_tokens = FakeRefreshTokenRepository()

    use_case = LoginUseCase(
        moderator_repository=moderators,
        refresh_token_repository=refresh_tokens,
        password_hasher=FakePasswordHasher(),
        jwt_service=FakeJwtService(),
        settings=make_settings(),
    )

    result = await use_case(LoginRequestSchema(email='mod@example.com', password='SecurePass123!'))

    assert result.user_id == moderator.id
    assert result.access_token == 'access-1'
    assert result.refresh_token == 'refresh-1'
    assert result.role == UserRole.MODERATOR
    assert refresh_tokens.created[0].user_id == moderator.id


@pytest.mark.anyio
async def test_login_rejects_invalid_password():
    moderators = FakeModeratorRepository()
    moderators.add(make_moderator_read_schema(email='mod@example.com', password_hash='hashed:SecurePass123!'))

    use_case = LoginUseCase(
        moderator_repository=moderators,
        refresh_token_repository=FakeRefreshTokenRepository(),
        password_hasher=FakePasswordHasher(),
        jwt_service=FakeJwtService(),
        settings=make_settings(),
    )

    with pytest.raises(InvalidCredentialsError):
        await use_case(LoginRequestSchema(email='mod@example.com', password='WrongPass123!'))


@pytest.mark.anyio
async def test_login_rejects_inactive_moderator():
    moderators = FakeModeratorRepository()
    moderators.add(
        make_moderator_read_schema(email='mod@example.com', password_hash='hashed:SecurePass123!', is_active=False)
    )

    use_case = LoginUseCase(
        moderator_repository=moderators,
        refresh_token_repository=FakeRefreshTokenRepository(),
        password_hasher=FakePasswordHasher(),
        jwt_service=FakeJwtService(),
        settings=make_settings(),
    )

    with pytest.raises(UserBlockedError):
        await use_case(LoginRequestSchema(email='mod@example.com', password='SecurePass123!'))


@pytest.mark.anyio
async def test_refresh_rotates_refresh_token():
    moderators = FakeModeratorRepository()
    moderator = make_moderator_read_schema()
    moderators.add(moderator)

    old_jti = uuid4()
    now = datetime.now(UTC)
    claims = JwtClaimsSchema(
        sub=moderator.id,
        role=moderator.role,
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
            user_id=moderator.id,
            issued_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    blacklist = FakeRefreshBlacklistRepository()

    use_case = RefreshUseCase(
        moderator_repository=moderators,
        refresh_token_repository=refresh_tokens,
        refresh_blacklist_repository=blacklist,
        jwt_service=jwt_service,
        settings=make_settings(),
    )

    result = await use_case(RefreshRequestSchema(refresh_token='old-refresh'))

    assert result.access_token == 'access-1'
    assert result.refresh_token == 'refresh-1'
    assert result.user_id == moderator.id
    assert result.role == moderator.role
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
            role=UserRole.MODERATOR,
            iat=1,
            exp=2,
            jti=old_jti,
        ),
    )
    blacklist = FakeRefreshBlacklistRepository()
    blacklist.jtis.add(old_jti)

    use_case = RefreshUseCase(
        moderator_repository=FakeModeratorRepository(),
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
            role=UserRole.MODERATOR,
            iat=1,
            exp=int((datetime.now(UTC) + timedelta(days=30)).timestamp()),
            jti=jti,
        ),
    )
    blacklist = FakeRefreshBlacklistRepository()

    use_case = LogoutUseCase(refresh_blacklist_repository=blacklist, jwt_service=jwt_service)

    await use_case(
        LogoutRequestSchema(refresh_token='refresh-token'),
        AuthenticatedUserSchema(id=user_id, role=UserRole.MODERATOR),
    )

    assert jti in blacklist.jtis


@pytest.mark.anyio
async def test_logout_rejects_refresh_token_from_another_user():
    jwt_service = FakeJwtService()
    jwt_service.set_decoded(
        'refresh-token',
        JwtClaimsSchema(
            sub=uuid4(),
            role=UserRole.MODERATOR,
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
            AuthenticatedUserSchema(id=uuid4(), role=UserRole.MODERATOR),
        )
