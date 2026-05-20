from shared.auth_lib.dependencies import get_current_user, require_role
from shared.auth_lib.enums import UserRole
from shared.auth_lib.jwt_service import JwtExpiredError, JwtInvalidError, JwtService
from shared.auth_lib.middleware import AuthMiddleware
from shared.auth_lib.password_hasher import PasswordHasher
from shared.auth_lib.protocols import AuthSettingsProtocol
from shared.auth_lib.schemas import (
    AuthenticatedUserSchema,
    IssuedTokenSchema,
    JwtClaimsSchema,
    TokenPairSchema,
)

__all__ = [
    'AuthMiddleware',
    'AuthSettingsProtocol',
    'AuthenticatedUserSchema',
    'IssuedTokenSchema',
    'JwtClaimsSchema',
    'JwtExpiredError',
    'JwtInvalidError',
    'JwtService',
    'PasswordHasher',
    'TokenPairSchema',
    'UserRole',
    'get_current_user',
    'require_role',
]
