from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import read_snapshot, transaction
from app.services import lease as lease_svc
from app.services.stats import water_level

router = APIRouter(tags=["leases"])


class OpenBody(BaseModel):
    session_code: str


class CloseBody(BaseModel):
    lease_no: str


@router.get("/leases")
def list_leases():
    # 列表与水位在同一快照内读出：不会出现「列表 3 行在途、水位写 2」的半截。
    with read_snapshot() as conn:
        rows = conn.execute(
            "SELECT * FROM leases ORDER BY id DESC"
        ).fetchall()
        return {"items": [dict(r) for r in rows], **water_level(conn)}


@router.get("/conflicts")
def list_conflicts():
    with read_snapshot() as conn:
        rows = conn.execute(
            "SELECT * FROM conflicts ORDER BY id DESC LIMIT 100"
        ).fetchall()
        # conflict_count 是总数（不受 LIMIT 影响），与总览同一聚合口径。
        return {"items": [dict(r) for r in rows], **water_level(conn)}


@router.post("/leases/open")
def open_lease(body: OpenBody):
    try:
        with transaction() as conn:
            result = lease_svc.open_lease(conn, body.session_code)
        if result.get("ok") is False:
            raise HTTPException(409, result.get("error") or "开窗冲突")
        return result
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/leases/close")
def close_lease(body: CloseBody):
    try:
        with transaction() as conn:
            return lease_svc.close_lease(conn, body.lease_no)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
