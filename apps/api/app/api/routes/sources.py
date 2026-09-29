from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings, get_user_config
from app.db.base import utcnow
from app.db.models import CollectorRun, SourceStatus
from app.db.session import get_db
from app.services.scan import collector_factories, run_collector

router = APIRouter(tags=["sources"])


def _run_out(r: CollectorRun) -> dict:
    return {"id": r.id, "source": r.source, "started_at": r.started_at, "finished_at": r.finished_at,
            "success": r.success, "duration_ms": r.duration_ms, "items_fetched": r.items_fetched,
            "items_matched": r.items_matched, "listings_evaluated": r.listings_evaluated,
            "deals_found": r.deals_found, "alerts_sent": r.alerts_sent, "error": r.error}


def source_health(db: Session) -> list[dict]:
    cfg = get_user_config().sources
    s = get_settings()
    configured = {
        "cardtrader": {"enabled": cfg.cardtrader.enabled, "interval_minutes": cfg.cardtrader.interval_minutes,
                       "mode": "mock" if s.cardtrader_is_mock else "live", "kind": "scheduled"},
        "stores": {"enabled": cfg.stores.enabled and any(x.enabled for x in cfg.stores.shops),
                   "interval_minutes": cfg.stores.interval_minutes, "mode": "live", "kind": "scheduled"},
        "finn": {"enabled": cfg.finn.enabled, "interval_minutes": None, "mode": "manual URL ingestion",
                 "kind": "manual"},
    }
    since = utcnow() - timedelta(hours=24)
    out = []
    for name, meta in configured.items():
        st = db.get(SourceStatus, name)
        runs = db.scalars(select(CollectorRun).where(CollectorRun.source == name, CollectorRun.started_at >= since)
                          .order_by(CollectorRun.started_at.desc())).all()
        last_ok = next((r for r in runs if r.success), None)
        failures = sum(1 for r in runs if not r.success)
        healthy = (st is None or st.consecutive_failures == 0) if meta["enabled"] else None
        out.append({
            "source": name, **meta, "healthy": healthy,
            "last_success": st.last_success if st else None, "last_failure": st.last_failure if st else None,
            "last_error": st.last_error if st else None,
            "consecutive_failures": st.consecutive_failures if st else 0,
            "running": bool(st and st.running_since),
            "runs_24h": len(runs), "error_rate_24h": round(failures / len(runs), 3) if runs else None,
            "last_duration_ms": last_ok.duration_ms if last_ok else None,
            "last_items_fetched": last_ok.items_fetched if last_ok else None,
            "last_items_matched": last_ok.items_matched if last_ok else None,
        })
    return out


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)) -> list[dict]:
    return source_health(db)


@router.get("/sources/{source}/runs")
def source_runs(source: str, db: Session = Depends(get_db), limit: int = Query(default=50, le=500)) -> list[dict]:
    rows = db.scalars(select(CollectorRun).where(CollectorRun.source == source)
                      .order_by(CollectorRun.started_at.desc()).limit(limit)).all()
    return [_run_out(r) for r in rows]


@router.post("/sources/{source}/run", status_code=202)
def trigger(source: str, background: BackgroundTasks) -> dict:
    if source not in collector_factories():
        raise HTTPException(404, "Unknown or non-scheduled source")
    background.add_task(run_collector, source)
    return {"queued": source}
