from __future__ import annotations

from fastapi import APIRouter

from app.db import read_snapshot
from app.services.stats import water_level

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard():
    # 总览只读水位聚合：与租约页/冲突页同一真源、同一快照口径。
    with read_snapshot() as conn:
        day_row = conn.execute(
            "SELECT value FROM settings WHERE key='fixture_day'"
        ).fetchone()
        day = day_row["value"] if day_row else None
        return {"fixture_day": day, **water_level(conn)}
