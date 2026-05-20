from dishka import Provider, Scope, provide

from apps.invoices.repositories import (
    InvoiceItemRepository,
    InvoiceRepository,
)
from apps.invoices.use_cases import CreateInvoiceUseCase


class InvoicesProvider(Provider):
    invoice_repository = provide(InvoiceRepository, scope=Scope.REQUEST)
    invoice_item_repository = provide(InvoiceItemRepository, scope=Scope.REQUEST)

    create_invoice_use_case = provide(CreateInvoiceUseCase, scope=Scope.REQUEST)
