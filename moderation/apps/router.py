from fastapi import APIRouter

from .auth.routers import router as auth_router
from .blocking_reasons.routers import router as blocking_reasons_router
from .events.routers import router as events_router
from .moderators.routers import router as moderators_router
from .queue.routers import router as queue_router
from .tickets.routers import router as tickets_router

router = APIRouter(prefix='/api/v1')

router.include_router(auth_router)
router.include_router(moderators_router)
router.include_router(blocking_reasons_router)
router.include_router(queue_router)
router.include_router(tickets_router)
router.include_router(events_router)
