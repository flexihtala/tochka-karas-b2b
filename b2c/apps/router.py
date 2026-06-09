from fastapi import APIRouter

from .addresses.routers import router as addresses_router
from .auth.routers import router as auth_router
from .buyers.routers import router as buyers_router
from .cart.routers import router as cart_router
from .catalog.routers import router as catalog_router
from .categories.routers import router as categories_router
from .favorites.routers import router as favorites_router
from .orders.routers import router as orders_router
from .payment_methods.routers import router as payment_methods_router

router = APIRouter(prefix='/api/v1')

router.include_router(auth_router)
router.include_router(buyers_router)
router.include_router(addresses_router)
router.include_router(payment_methods_router)
router.include_router(catalog_router)
router.include_router(cart_router)
router.include_router(orders_router)
router.include_router(categories_router)
router.include_router(favorites_router)
