from fastapi import APIRouter
from .auth.routers import router as auth_router
from .events.routers import router as moderation_router
from .inventory.routers import router as inventory_router
from .products.routers import router as products_router
from .public.routers import router as public_router
from .skus.routers import router as skus_router

router = APIRouter(prefix='/api/v1')

router.include_router(auth_router)
router.include_router(products_router)
router.include_router(public_router)
router.include_router(skus_router)
router.include_router(inventory_router)
router.include_router(moderation_router)
