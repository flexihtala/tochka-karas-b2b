from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field, model_validator


class FieldReportSchema(BaseModel):
    """Замечание модератора к конкретному полю товара.

    Канонная форма (canon moderation-flows.md#soft-block): field_name (enum из 7 значений:
    title, description, product_images, category, sku_name, sku_image, sku_price),
    sku_id (опц., null = замечание к товару), comment (обяз., max 500).

    Для обратной совместимости со старой спекой `neomarket-moderation.yaml` принимается
    и legacy-форма: field_path + message (ключ message маппится в канонический атрибут
    comment через AliasChoices; legacy-ключ severity игнорируется).

    Замечание должно содержать хотя бы одно из: field_name (канон) или field_path (legacy).
    Соответствие field_name enum'у FieldReportName проверяет use-case и поднимает
    InvalidFieldNameError (400) — чтобы ошибка отдавалась в едином формате code/message.
    """

    field_name: str | None = None
    field_path: str | None = Field(default=None, min_length=1)
    sku_id: UUID | None = None
    comment: str = Field(min_length=1, max_length=500, validation_alias=AliasChoices('comment', 'message'))

    @model_validator(mode='after')
    def _check_field_reference(self) -> 'FieldReportSchema':
        if self.field_name is None and self.field_path is None:
            raise ValueError('Замечание должно содержать field_name (канон) или field_path (legacy)')
        return self


class ApproveTicketRequestSchema(BaseModel):
    """POST /api/v1/tickets/{id}/approve — опциональное тело по спеке.

    Поле comment (maxLength 2000) — опциональный комментарий модератора при одобрении.
    """

    comment: str | None = Field(default=None, max_length=2000)


class BlockTicketRequestSchema(BaseModel):
    """POST /api/v1/tickets/{id}/block — тело запроса (BlockDecisionRequest по спеке).

    blocking_reason_ids — массив (minItems: 1) UUID причин.
    comment — опциональный комментарий модератора (maxLength 2000).
    hard_block выводится из выбранной причины — не передаётся в теле.
    """

    blocking_reason_ids: list[UUID] = Field(min_length=1)
    comment: str | None = Field(default=None, max_length=2000)
    field_reports: list[FieldReportSchema] | None = None


class DeclineProductRequestSchema(BaseModel):
    """POST /api/v1/products/{product_id}/decline — канонное тело MOD-4 (мягкая блокировка).

    blocking_reason_id — ОДНА причина (канон); оборачивается в список для внутреннего
    BlockTicketUseCase. moderator_comment — обязательный общий комментарий (max 1000).
    field_reports — замечания по полям (default []).
    """

    blocking_reason_id: UUID
    moderator_comment: str = Field(min_length=1, max_length=1000)
    field_reports: list[FieldReportSchema] = Field(default_factory=list)
