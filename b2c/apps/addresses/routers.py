from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response, status

from apps.addresses.schemas import (
    AddressCreateRequestSchema,
    AddressResponseSchema,
    AddressUpdateRequestSchema,
)
from apps.addresses.use_cases import (
    CreateAddressUseCase,
    DeleteAddressUseCase,
    ListAddressesUseCase,
    UpdateAddressUseCase,
)
from apps.auth.schemas import ErrorResponseSchema
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/buyers/me/addresses')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


@router.get('', response_model=list[AddressResponseSchema], responses=error_responses)
@inject
async def list_addresses(
    use_case: FromDishka[ListAddressesUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> list[AddressResponseSchema]:
    return await use_case(current_user)


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    response_model=AddressResponseSchema,
    responses=error_responses,
)
@inject
async def create_address(
    data: AddressCreateRequestSchema,
    use_case: FromDishka[CreateAddressUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> AddressResponseSchema:
    return await use_case(data, current_user)


@router.patch('/{address_id}', response_model=AddressResponseSchema, responses=error_responses)
@inject
async def update_address(
    address_id: UUID,
    data: AddressUpdateRequestSchema,
    use_case: FromDishka[UpdateAddressUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> AddressResponseSchema:
    return await use_case(address_id, data, current_user)


@router.delete('/{address_id}', status_code=status.HTTP_204_NO_CONTENT, responses=error_responses)
@inject
async def delete_address(
    address_id: UUID,
    use_case: FromDishka[DeleteAddressUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> Response:
    await use_case(address_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
