from fastapi import Request

from apps.auth.errors import UnauthorizedError
from shared.auth_lib import AuthenticatedUserSchema


def get_current_user(request: Request) -> AuthenticatedUserSchema:
    """Возвращает пользователя из request.state.user (выставленного AuthMiddleware).

    Кидает локальный UnauthorizedError (плоский формат), чтобы соответствовать стилю b2b/moderation.
    """
    user = getattr(request.state, 'user', None)
    if user is None:
        raise UnauthorizedError()
    return user
