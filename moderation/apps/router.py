from fastapi import APIRouter

from .auth.routers import router as auth_router
from .events.routers import router as events_router
from .moderators.routers import router as moderators_router
from .stats.routers import router as stats_router

router = APIRouter(prefix='/api/v1')

router.include_router(auth_router)
router.include_router(moderators_router)
router.include_router(stats_router)
router.include_router(events_router)
