"""水位聚合：唯一真源 = 租约表 + 冲突表。

本模块是全项目计算「在途租约」「冲突计数」「上课中/待开窗」的唯一次入口。
任何页面或只读接口都不得另起 COUNT，也不得读取缓存表作为展示真源；
开窗/关窗/冲突写入路径只写 leases/conflicts，不得单独改水位表冒充成功。
调用方必须在同一读快照内调用（见 app.db.read_snapshot）。
"""
from __future__ import annotations

import sqlite3


def water_level(conn: sqlite3.Connection) -> dict:
    open_leases = conn.execute(
        "SELECT COUNT(*) c FROM leases WHERE status='open'"
    ).fetchone()["c"]
    conflicts = conn.execute("SELECT COUNT(*) c FROM conflicts").fetchone()["c"]
    live_sessions = conn.execute(
        "SELECT COUNT(*) c FROM sessions WHERE status='live'"
    ).fetchone()["c"]
    draft_sessions = conn.execute(
        "SELECT COUNT(*) c FROM sessions WHERE status='draft'"
    ).fetchone()["c"]
    return {
        "open_leases": int(open_leases),
        "conflict_count": int(conflicts),
        "live_sessions": int(live_sessions),
        "draft_sessions": int(draft_sessions),
    }
