"""AuthMiddleware: декодирует Bearer-токен → request.state.user.

Не блокирует анонимные запросы — endpoints сами решают через get_current_user.
"""

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from shared.auth_lib.jwt_service import JwtExpiredError, JwtInvalidError, JwtService
from shared.auth_lib.schemas import AuthenticatedUserSchema


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, jwt_service: JwtService):
        super().__init__(app)
        self.jwt_service = jwt_service

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.user = None
        authorization = request.headers.get('Authorization', '')

        if not authorization:
            return await call_next(request)
        if not authorization.startswith('Bearer '):
            return JSONResponse(
                status_code=401,
                content={'error': {'code': 'INVALID_TOKEN', 'message': 'Invalid token'}},
            )

        try:
            claims = self.jwt_service.decode(authorization[7:])
        except JwtExpiredError:
            return JSONResponse(
                status_code=401,
                content={'error': {'code': 'TOKEN_EXPIRED', 'message': 'Token expired'}},
            )
        except JwtInvalidError:
            return JSONResponse(
                status_code=401,
                content={'error': {'code': 'INVALID_TOKEN', 'message': 'Invalid token'}},
            )

        request.state.user = AuthenticatedUserSchema(id=claims.sub, role=claims.role)
        return await call_next(request)
