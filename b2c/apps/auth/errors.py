from apps.errors import AppError


class AuthError(AppError):
    pass


class InvalidRequestError(AuthError):
    def __init__(self, message: str = 'Невалидное тело запроса'):
        super().__init__('INVALID_REQUEST', message, 400)


class InvalidTokenError(AuthError):
    def __init__(self, message: str = 'Невалидный токен'):
        super().__init__('INVALID_TOKEN', message, 401)


class TokenExpiredError(AuthError):
    def __init__(self, message: str = 'Токен истёк'):
        super().__init__('TOKEN_EXPIRED', message, 401)


class TokenRevokedError(AuthError):
    def __init__(self, message: str = 'Refresh-токен отозван'):
        super().__init__('TOKEN_REVOKED', message, 401)


class InvalidCredentialsError(AuthError):
    def __init__(self, message: str = 'Неверный email или пароль'):
        super().__init__('INVALID_CREDENTIALS', message, 401)


class UnauthorizedError(AuthError):
    def __init__(self, message: str = 'Нет заголовка Authorization'):
        super().__init__('UNAUTHORIZED', message, 401)


class UserBlockedError(AuthError):
    def __init__(self, message: str = 'Пользователь заблокирован'):
        super().__init__('USER_BLOCKED', message, 403)


class EmailAlreadyExistsError(AuthError):
    def __init__(self, message: str = 'Email уже зарегистрирован'):
        super().__init__('EMAIL_ALREADY_EXISTS', message, 409)
