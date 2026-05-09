from uuid import UUID

from apps.products.errors import InvalidProductRequestError


def validate_title(title: str | None) -> str:
    if title is None or not title.strip():
        raise InvalidProductRequestError('title is required')
    title = title.strip()
    if len(title) > 255:
        raise InvalidProductRequestError('title must be 1-255 characters')
    return title


def validate_description(description: str | None) -> str:
    if description is None or not description.strip():
        raise InvalidProductRequestError('description is required')
    description = description.strip()
    if len(description) > 5000:
        raise InvalidProductRequestError('description must be 1-5000 characters')
    return description


def validate_category_id(category_id: str | None) -> UUID:
    if category_id is None:
        raise InvalidProductRequestError('category_id is required')
    try:
        return UUID(category_id)
    except ValueError as exc:
        raise InvalidProductRequestError('category_id must be a valid UUID') from exc
