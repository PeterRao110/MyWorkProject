from fastapi import APIRouter

from app.controllers.health import get_health

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return get_health()
