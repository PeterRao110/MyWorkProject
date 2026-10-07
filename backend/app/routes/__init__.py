from fastapi import APIRouter

from app.routes.health import router as health_router
from app.routes.schedule import router as schedule_router
from app.routes.settings import router as settings_router
from app.routes.tushare import router as tushare_router

router = APIRouter()
router.include_router(health_router)
router.include_router(schedule_router)
router.include_router(settings_router)
router.include_router(tushare_router)
