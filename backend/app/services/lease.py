from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.services.ready import readiness, resource_busy
from app.services.stats import water_level


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _conflict_mode(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT value FROM settings WHERE key='conflict_mode'"
    ).fetchone()
    return row["value"] if row else "reject"


def open_lease(conn: sqlite3.Connection, session_code: str) -> dict:
    """开窗。冲突臂只写 conflicts 行；成功臂只写 leases 行 + 会话状态。

    两条臂都不碰任何计数表——水位由同事务写入的事实行聚合得出，
    因此开窗 +1 / 冲突加计天然与写路径同源，不存在「改水位冒充成功」。
    """
    session = conn.execute(
        "SELECT * FROM sessions WHERE code=?", (session_code,)
    ).fetchone()
    if session is None:
        raise ValueError(f"批窗不存在：{session_code}")
    if session["status"] == "live":
        raise ValueError("批窗已在上课，勿重复开窗")
    if session["status"] == "done":
        raise ValueError("批窗已结束")

    ready = readiness(conn, session)
    if not ready["ready"]:
        mode = _conflict_mode(conn)
        for reason in ready["reasons"]:
            kind = "room" if "算力槽" in reason else ("teacher" if "执行器" in reason else "ready")
            resource = (
                session["room_code"]
                if kind == "room"
                else (session["teacher_code"] if kind == "teacher" else session_code)
            )
            # 一次冲突事件 = conflicts 一行；冲突计数由该行聚合，无需再加计。
            conn.execute(
                "INSERT INTO conflicts(kind, session_code, resource_code, day, start_min, end_min, reason, created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    kind,
                    session_code,
                    resource,
                    session["day"],
                    session["start_min"],
                    session["end_min"],
                    reason,
                    _now(),
                ),
            )
        # 底座贯彻 reject（冲突落库后由调用方提交）；候补算力槽留给后续题
        return {
            "ok": False,
            "error": "；".join(ready["reasons"]),
            "conflict_mode": mode,
            **water_level(conn),
        }

    if resource_busy(
        conn,
        kind="room",
        resource_code=session["room_code"],
        day=session["day"],
        start_min=session["start_min"],
        end_min=session["end_min"],
    ) or resource_busy(
        conn,
        kind="teacher",
        resource_code=session["teacher_code"],
        day=session["day"],
        start_min=session["start_min"],
        end_min=session["end_min"],
    ):
        raise ValueError("资源刚被占用，开窗失败")

    n = conn.execute("SELECT COUNT(*) c FROM leases").fetchone()["c"] + 1
    lease_no = f"L-{session['day'].replace('-', '')}-{n:04d}"
    conn.execute(
        "INSERT INTO leases(lease_no, session_code, room_code, teacher_code, day, start_min, end_min, status, opened_at) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (
            lease_no,
            session_code,
            session["room_code"],
            session["teacher_code"],
            session["day"],
            session["start_min"],
            session["end_min"],
            "open",
            _now(),
        ),
    )
    conn.execute(
        "UPDATE sessions SET status='live' WHERE code=?", (session_code,)
    )
    return {
        "ok": True,
        "lease_no": lease_no,
        "session_code": session_code,
        "status": "open",
        **water_level(conn),
    }


def close_lease(conn: sqlite3.Connection, lease_no: str) -> dict:
    lease = conn.execute(
        "SELECT * FROM leases WHERE lease_no=?", (lease_no,)
    ).fetchone()
    if lease is None:
        raise ValueError(f"租约不存在：{lease_no}")
    if lease["status"] != "open":
        raise ValueError("租约不在占用态")
    conn.execute(
        "UPDATE leases SET status='closed', closed_at=? WHERE lease_no=?",
        (_now(), lease_no),
    )
    conn.execute(
        "UPDATE sessions SET status='done' WHERE code=?",
        (lease["session_code"],),
    )
    return {
        "lease_no": lease_no,
        "status": "closed",
        **water_level(conn),
    }
