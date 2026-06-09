from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from apps.auth.schemas.moderator import ModeratorCreateSchema, ModeratorReadSchema, ModeratorUpdateSchema
from apps.auth.schemas.refresh_blacklist import RefreshBlacklistCreateSchema
from apps.auth.schemas.refresh_token import RefreshTokenCreateSchema, RefreshTokenReadSchema
from shared.auth_lib import (
    IssuedTokenSchema,
    JwtClaimsSchema,
    JwtExpiredError,
    JwtInvalidError,
    TokenPairSchema,
    UserRole,
)


def make_moderator_read_schema(
    *,
    id: UUID | None = None,
    email: str = 'mod@example.com',
    password_hash: str = 'hashed-password',
    role: UserRole = UserRole.MODERATOR,
    is_active: bool = True,
    first_name: str = 'Ivan',
    last_name: str | None = 'Ivanov',
) -> ModeratorReadSchema:
    now = datetime.now(UTC)
    return ModeratorReadSchema(
        id=id or uuid4(),
        email=email,
        password_hash=password_hash,
        role=role,
        is_active=is_active,
        first_name=first_name,
        last_name=last_name,
        password_changed_at=None,
        created_at=now,
        updated_at=now,
    )


class FakeModeratorRepository:
    def __init__(self):
        self.by_id: dict[UUID, ModeratorReadSchema] = {}
        self.by_email: dict[str, ModeratorReadSchema] = {}
        self.created: list[ModeratorCreateSchema] = []
        self.updated: list[ModeratorUpdateSchema] = []

    async def create(self, data: ModeratorCreateSchema) -> ModeratorReadSchema:
        self.created.append(data)
        moderator = make_moderator_read_schema(
            id=data.id or uuid4(),
            email=data.email,
            password_hash=data.password_hash,
            role=data.role,
            is_active=data.is_active,
            first_name=data.first_name,
            last_name=data.last_name,
        )
        self.add(moderator)
        return moderator

    async def get_by_email(self, email: str) -> ModeratorReadSchema | None:
        return self.by_email.get(email)

    async def get_or_none(self, id_: UUID) -> ModeratorReadSchema | None:
        return self.by_id.get(id_)

    async def update(self, data: ModeratorUpdateSchema) -> ModeratorReadSchema | None:
        existing = self.by_id.get(data.id)
        if existing is None:
            return None
        self.updated.append(data)
        update_payload = data.model_dump(exclude_unset=True, exclude={'id'})
        for key, value in update_payload.items():
            setattr(existing, key, value)
        self.by_id[data.id] = existing
        self.by_email[existing.email] = existing
        return existing

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        is_active: bool | None = None,
    ) -> tuple[list[ModeratorReadSchema], int]:
        items = list(self.by_id.values())
        if is_active is not None:
            items = [m for m in items if m.is_active == is_active]
        total_count = len(items)
        items.sort(key=lambda m: m.created_at, reverse=True)
        return items[offset : offset + limit], total_count

    def add(self, moderator: ModeratorReadSchema) -> None:
        self.by_id[moderator.id] = moderator
        self.by_email[moderator.email] = moderator


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
