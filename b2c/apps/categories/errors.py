from apps.errors import AppError


class CategoryError(AppError):
    pass


class CategoryNotFoundError(CategoryError):
    def __init__(self, message: str = 'Категория не найдена'):
        super().__init__('NOT_FOUND', message, 404)


class AmbiguousBreadcrumbsParamsError(CategoryError):
    def __init__(self, message: str = 'Можно передать только один параметр: category_id или product_id'):
        super().__init__('ambiguous_param', message, 400)


class MissingBreadcrumbsParamsError(CategoryError):
    def __init__(self, message: str = 'Требуется category_id или product_id'):
        super().__init__('missing_param', message, 400)


class OrphanCategoryNodeError(CategoryError):
    def __init__(self, message: str = 'Иерархия категорий нарушена'):
        super().__init__('orphan_node', message, 422)
