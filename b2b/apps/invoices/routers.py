from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from apps.auth.schemas import ErrorResponseSchema
from apps.invoices.schemas.request import InvoiceCreateRequestSchema
from apps.invoices.schemas.response import InvoiceResponseSchema
from apps.invoices.use_cases import CreateInvoiceUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/invoices')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    response_model=InvoiceResponseSchema,
    responses=error_responses,
)
@inject
async def create_invoice(
    data: InvoiceCreateRequestSchema,
    use_case: FromDishka[CreateInvoiceUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.SELLER)),
) -> InvoiceResponseSchema:
    return await use_case(data, current_user)
