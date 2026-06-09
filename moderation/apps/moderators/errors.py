from apps.errors import AppError


class ModeratorError(AppError):
    pass


class ModeratorNotFoundError(ModeratorError):
    def __init__(self, message: str = 'Модератор не найден'):
        super().__init__('MODERATOR_NOT_FOUND', message, 404)


class EmailAlreadyExistsError(ModeratorError):
    def __init__(self, message: str = 'Email уже зарегистрирован'):
        super().__init__('EMAIL_ALREADY_EXISTS', message, 409)
