from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import get_settings, get_user_config
from app.db.session import get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/ready")
def ready(response: Response) -> dict:
    """Readiness: DB reachable, migrations at head, config valid."""
    checks: dict[str, str] = {}
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
            try:
                current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            except Exception:
                current = None
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        from app.core.config import REPO_ROOT

        ini = REPO_ROOT / "apps" / "api" / "alembic.ini"
        head = ScriptDirectory.from_config(Config(str(ini))).get_current_head() if ini.exists() else None
        checks["migrations"] = "ok" if current and current == head else f"pending (db={current}, head={head})"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"
    try:
        get_user_config()
        checks["config"] = "ok"
    except Exception as exc:
        checks["config"] = f"error: {type(exc).__name__}: {exc}"[:300]
    s = get_settings()
    checks["cardtrader_mode"] = "mock" if s.cardtrader_is_mock else "live"
    checks["telegram_mode"] = "dry-run" if s.telegram_is_dry_run else "live"
    ok = all(v == "ok" for k, v in checks.items() if k in ("database", "migrations", "config"))
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ok else "not_ready", "checks": checks}
