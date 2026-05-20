from fastapi import APIRouter

from .addresses.routers import router as addresses_router
from .auth.routers import router as auth_router
from .buyers.routers import router as buyers_router
from .favorites.routers import router as favorites_router
from .payment_methods.routers import router as payment_methods_router

router = APIRouter(prefix='/api/v1')

router.include_router(auth_router)
router.include_router(buyers_router)
router.include_router(addresses_router)
router.include_router(payment_methods_router)
router.include_router(favorites_router)
