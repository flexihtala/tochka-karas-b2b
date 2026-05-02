from fastapi import Request

from apps.auth.errors import UnauthorizedError
from apps.auth.schemas.token import AuthenticatedUserSchema


def get_current_user(request: Request) -> AuthenticatedUserSchema:
    user = getattr(request.state, 'user', None)
    if user is None:
        raise UnauthorizedError()
    return user
