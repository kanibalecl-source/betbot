from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import get_settings
from app.core.security import require_api_key
from app.data.postgres_repository import (
    DatabaseUnavailable,
    health,
    initialize_schema,
    list_picks,
    status_document,
    sync_metrics,
    sync_snapshot,
)
from app.domain.schemas import Discipline, SyncEnvelope, SyncResult


router = APIRouter(dependencies=[Depends(require_api_key)])


def _unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Analytical database unavailable: {type(exc).__name__}",
    )


@router.get("/picks")
def picks(
    discipline: Discipline,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1),
    status_filter: str | None = Query(default=None, alias="status"),
):
    size = min(page_size, get_settings().api_max_page_size)
    try:
        return list_picks(discipline, page, size, status_filter)
    except DatabaseUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/sports/{discipline}/summary")
def sport_summary(discipline: Discipline):
    try:
        return {
            "discipline": discipline,
            "quality": status_document(discipline, "quality"),
            "model": status_document(discipline, "model"),
            "data_quality": status_document(discipline, "data_quality"),
            "runtime": status_document(discipline, "runtime"),
        }
    except DatabaseUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/quality/status")
def quality_status(discipline: Discipline = "football"):
    try:
        return status_document(discipline, "quality")
    except DatabaseUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/models/status")
def models_status(discipline: Discipline = "football"):
    try:
        return status_document(discipline, "model")
    except DatabaseUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/data-quality/report")
def data_quality_report(discipline: Discipline = "football"):
    try:
        return status_document(discipline, "data_quality")
    except DatabaseUnavailable as exc:
        raise _unavailable(exc) from exc


@router.get("/monitoring")
def monitoring():
    try:
        return {"database": health(), "sync": sync_metrics()}
    except DatabaseUnavailable as exc:
        raise _unavailable(exc) from exc


@router.post("/internal/sync", response_model=SyncResult)
def internal_sync(payload: SyncEnvelope) -> SyncResult:
    if not get_settings().api_sync_enabled:
        raise HTTPException(status_code=403, detail="Snapshot synchronization is disabled")
    try:
        initialize_schema()
        return SyncResult(**sync_snapshot(payload.records, payload.statuses, payload.source))
    except DatabaseUnavailable as exc:
        raise _unavailable(exc) from exc
