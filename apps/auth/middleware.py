from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from apps.auth.schemas.token import AuthenticatedUserSchema
from apps.auth.services.jwt_service import JwtExpiredError, JwtInvalidError, JwtService


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, jwt_service: JwtService):
        super().__init__(app)
        self.jwt_service = jwt_service

    async def dispatch(self, request: Request, call_next):
        request.state.user = None
        authorization = request.headers.get('Authorization', '')

        if not authorization:
            return await call_next(request)
        if not authorization.startswith('Bearer '):
            return JSONResponse(status_code=401, content={'code': 'INVALID_TOKEN', 'message': 'Невалидный токен'})

        try:
            claims = self.jwt_service.decode(authorization[7:])
        except JwtExpiredError:
            return JSONResponse(status_code=401, content={'code': 'TOKEN_EXPIRED', 'message': 'Токен истёк'})
        except JwtInvalidError:
            return JSONResponse(status_code=401, content={'code': 'INVALID_TOKEN', 'message': 'Невалидный токен'})

        request.state.user = AuthenticatedUserSchema(id=claims.sub, role=claims.role)
        return await call_next(request)
