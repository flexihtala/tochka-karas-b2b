from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from apps.auth.enums import UserRole
from apps.auth.schemas.refresh_blacklist import RefreshBlacklistCreateSchema
from apps.auth.schemas.refresh_token import RefreshTokenCreateSchema, RefreshTokenReadSchema
from apps.auth.schemas.token import IssuedTokenSchema, JwtClaimsSchema, TokenPairSchema
from apps.auth.schemas.user import UserCreateSchema, UserReadSchema
from apps.auth.services.jwt_service import JwtExpiredError, JwtInvalidError


def make_user_read_schema(
    *,
    id: UUID | None = None,
    email: str = 'seller@example.com',
    password_hash: str = 'hashed-password',
    role: UserRole = UserRole.SELLER,
    is_active: bool = True,
) -> UserReadSchema:
    now = datetime.now(UTC)
    return UserReadSchema(
        id=id or uuid4(),
        email=email,
        password_hash=password_hash,
        role=role,
        is_active=is_active,
        password_changed_at=None,
        company_name='OOO Primer',
        inn='7707083893',
        first_name='Ivan',
        last_name='Ivanov',
        phone='+79001234567',
        created_at=now,
        updated_at=now,
    )


class FakeUserRepository:
    def __init__(self):
        self.users_by_id: dict[UUID, UserReadSchema] = {}
        self.users_by_email: dict[str, UserReadSchema] = {}
        self.users_by_inn: dict[str, UserReadSchema] = {}
        self.created: list[UserCreateSchema] = []

    async def create(self, data: UserCreateSchema) -> UserReadSchema:
        self.created.append(data)
        user = make_user_read_schema(
            id=data.id or uuid4(),
            email=data.email,
            password_hash=data.password_hash,
            role=data.role,
            is_active=data.is_active,
        )
        user.company_name = data.company_name
        user.inn = data.inn
        user.first_name = data.first_name
        user.last_name = data.last_name
        user.phone = data.phone
        self.add(user)
        return user

    async def get_by_email(self, email: str) -> UserReadSchema | None:
        return self.users_by_email.get(email)

    async def get_by_inn(self, inn: str) -> UserReadSchema | None:
        return self.users_by_inn.get(inn)

    async def get_or_none(self, id_: UUID) -> UserReadSchema | None:
        return self.users_by_id.get(id_)

    def add(self, user: UserReadSchema) -> None:
        self.users_by_id[user.id] = user
        self.users_by_email[user.email] = user
        if user.inn:
            self.users_by_inn[user.inn] = user


class FakeRefreshTokenRepository:
    def __init__(self):
        self.tokens: dict[UUID, RefreshTokenReadSchema] = {}
        self.created: list[RefreshTokenCreateSchema] = []
        self.deleted: list[UUID] = []

    async def create(self, data: RefreshTokenCreateSchema) -> RefreshTokenReadSchema:
        self.created.append(data)
        token = RefreshTokenReadSchema(
            id=data.jti,
            jti=data.jti,
            user_id=data.user_id,
            issued_at=data.issued_at,
            expires_at=data.expires_at,
        )
        self.tokens[token.jti] = token
        return token

    async def get_by_jti(self, jti: UUID) -> RefreshTokenReadSchema | None:
        return self.tokens.get(jti)

    async def delete_by_jti(self, jti: UUID) -> bool:
        self.deleted.append(jti)
        return self.tokens.pop(jti, None) is not None


class FakeRefreshBlacklistRepository:
    def __init__(self):
        self.jtis: set[UUID] = set()
        self.created: list[RefreshBlacklistCreateSchema] = []

    async def create(self, data: RefreshBlacklistCreateSchema):
        self.created.append(data)
        self.jtis.add(data.jti)
        return data

    async def exists(self, jti: UUID) -> bool:
        return jti in self.jtis


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f'hashed:{password}'

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == self.hash(password)


class FakeJwtService:
    def __init__(self):
        self.decoded: dict[str, JwtClaimsSchema | Exception] = {}
        self.issued_pairs: list[TokenPairSchema] = []

    def issue_token_pair(self, user_id: UUID, role: UserRole) -> TokenPairSchema:
        now = datetime.now(UTC)
        pair_index = len(self.issued_pairs) + 1
        pair = TokenPairSchema(
            access=IssuedTokenSchema(
                value=f'access-{pair_index}',
                claims=JwtClaimsSchema(
                    sub=user_id,
                    role=role,
                    iat=int(now.timestamp()),
                    exp=int((now + timedelta(hours=1)).timestamp()),
                    jti=uuid4(),
                ),
            ),
            refresh=IssuedTokenSchema(
                value=f'refresh-{pair_index}',
                claims=JwtClaimsSchema(
                    sub=user_id,
                    role=role,
                    iat=int(now.timestamp()),
                    exp=int((now + timedelta(days=30)).timestamp()),
                    jti=uuid4(),
                ),
            ),
        )
        self.issued_pairs.append(pair)
        return pair

    def decode(self, token: str) -> JwtClaimsSchema:
        result = self.decoded.get(token)
        if isinstance(result, Exception):
            raise result
        if result is None:
            raise JwtInvalidError()
        return result

    def set_decoded(self, token: str, claims: JwtClaimsSchema) -> None:
        self.decoded[token] = claims

    def set_expired(self, token: str) -> None:
        self.decoded[token] = JwtExpiredError()
