from apps.blocking_reasons.errors import BlockingReasonAlreadyExistsError
from apps.blocking_reasons.repositories import BlockingReasonRepository
from apps.blocking_reasons.schemas.db import BlockingReasonCreateSchema
from apps.blocking_reasons.schemas.request import BlockingReasonCreateRequestSchema
from apps.blocking_reasons.schemas.response import BlockingReasonResponseSchema


class CreateBlockingReasonUseCase:
    """POST /api/v1/blocking-reasons — admin-only.

    code должно быть уникальным; при коллизии — 409.
    """

    def __init__(self, blocking_reason_repository: BlockingReasonRepository):
        self.blocking_reason_repository = blocking_reason_repository

    async def __call__(self, data: BlockingReasonCreateRequestSchema) -> BlockingReasonResponseSchema:
        if await self.blocking_reason_repository.get_by_code(data.code):
            raise BlockingReasonAlreadyExistsError()

        reason = await self.blocking_reason_repository.create(
            BlockingReasonCreateSchema(
                code=data.code,
                title=data.title,
                description=data.description,
                hard_block=data.hard_block,
            )
        )
        return BlockingReasonResponseSchema.model_validate(reason)
