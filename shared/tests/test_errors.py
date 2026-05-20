from shared.errors import AppError, ErrorCode
from shared.errors.base import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError


def test_app_error_to_payload_minimal():
    err = AppError('boom')
    payload = err.to_payload()
    assert payload == {'error': {'code': str(ErrorCode.INTERNAL), 'message': 'boom'}}


def test_app_error_with_details():
    err = AppError('boom', code='X', status_code=418, details={'a': 1})
    payload = err.to_payload()
    assert payload == {'error': {'code': 'X', 'message': 'boom', 'details': {'a': 1}}}


def test_typed_errors_have_expected_status_codes():
    assert UnauthorizedError().status_code == 401
    assert ForbiddenError().status_code == 403
    assert NotFoundError().status_code == 404
    assert ConflictError().status_code == 409
