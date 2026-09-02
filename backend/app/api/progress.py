import uuid

from fastapi import APIRouter, Response

from app.dependencies import CurrentAuth, Database
from app.schemas import DashboardData, ProgressData
from app.services.analytics import dashboard_data, progress_data

router = APIRouter(tags=["progress"])


@router.get("/dashboard", response_model=DashboardData)
async def dashboard(
    auth: CurrentAuth,
    db: Database,
    response: Response,
    deck_id: uuid.UUID | None = None,
) -> DashboardData:
    response.headers["Cache-Control"] = "private, no-store"
    return await dashboard_data(db, auth.user, deck_id)


@router.get("/progress", response_model=ProgressData)
async def progress(
    auth: CurrentAuth,
    db: Database,
    response: Response,
    deck_id: uuid.UUID | None = None,
) -> ProgressData:
    response.headers["Cache-Control"] = "private, no-store"
    return await progress_data(db, auth.user, deck_id)
