"""Smoke-тесты JwtService — issue/decode round-trip + проверки ошибок."""

import uuid
from dataclasses import dataclass

import pytest

from shared.auth_lib import JwtExpiredError, JwtInvalidError, JwtService, UserRole


@dataclass
class FakeSettings:
    jwt_algorithm: str = 'HS256'
    jwt_secret: str = 'test-secret-must-be-at-least-32-chars-long-xxx'
    jwt_private_key: str | None = None
    jwt_public_key: str | None = None
    access_token_ttl_seconds: int = 3600
    refresh_token_ttl_seconds: int = 86400


def test_issue_and_decode_round_trip():
    service = JwtService(FakeSettings())
    user_id = uuid.uuid4()
    pair = service.issue_token_pair(user_id, UserRole.SELLER)

    decoded = service.decode(pair.access.value)
    assert decoded.sub == user_id
    assert decoded.role == UserRole.SELLER


def test_decode_rejects_garbage():
    service = JwtService(FakeSettings())
    with pytest.raises(JwtInvalidError):
        service.decode('not-a-jwt')


def test_decode_rejects_token_signed_with_other_secret():
    issuer = JwtService(FakeSettings(jwt_secret='secret-A-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx'))
    decoder = JwtService(FakeSettings(jwt_secret='secret-B-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx'))

    token = issuer.issue_token(uuid.uuid4(), UserRole.SELLER, ttl_seconds=60)
    with pytest.raises(JwtInvalidError):
        decoder.decode(token.value)


def test_expired_token():
    service = JwtService(FakeSettings(access_token_ttl_seconds=-1, refresh_token_ttl_seconds=-1))
    token = service.issue_token(uuid.uuid4(), UserRole.SELLER, ttl_seconds=-1)
    with pytest.raises(JwtExpiredError):
        service.decode(token.value)
