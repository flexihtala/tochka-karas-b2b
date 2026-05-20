"""FastAPI-зависимости для аутентификации/авторизации."""

from collections.abc import Callable

from fastapi import Request

from shared.auth_lib.enums import UserRole
from shared.auth_lib.schemas import AuthenticatedUserSchema
from shared.errors.base import ForbiddenError, UnauthorizedError


def get_current_user(request: Request) -> AuthenticatedUserSchema:
    """Возвращает пользователя из request.state.user (выставленного AuthMiddleware).

    Raises:
        UnauthorizedError: если запрос анонимный или middleware не отработал.
    """
    user = getattr(request.state, 'user', None)
    if user is None:
        raise UnauthorizedError()
    return user


def require_role(*roles: UserRole) -> Callable[[Request], AuthenticatedUserSchema]:
    """Фабрика-зависимость: пропускает только пользователей с указанными ролями.

    Использование:
        @router.post('/products', dependencies=[Depends(require_role(UserRole.SELLER))])
        async def create_product(user: AuthenticatedUserSchema = Depends(get_current_user)):
            ...
    """

    def _dep(request: Request) -> AuthenticatedUserSchema:
        user = get_current_user(request)
        if user.role not in roles:
            raise ForbiddenError(
                message=f'Role {user.role!s} not allowed; requires one of {[r.value for r in roles]}'
            )
        return user

    return _dep
