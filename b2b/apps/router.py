from fastapi import APIRouter
from .auth.routers import router as auth_router
from .invoices.routers import router as invoices_router
from .products.routers import router as products_router
from .skus.routers import router as skus_router

router = APIRouter(prefix='/api/v1')

router.include_router(auth_router)
router.include_router(products_router)
router.include_router(skus_router)
router.include_router(invoices_router)
