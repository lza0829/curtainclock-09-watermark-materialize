# -*- coding: utf-8 -*-
"""API smoke against a running API (default 127.0.0.1:11100).

Checks the single-source rule for the water level:
  * 唯一真源 = leases(status='open') + conflicts 聚合
  * 开窗 +1 / 关窗 -1，冲突加计
  * 水位表被禁止（不存在）；即使手工建表写假值，展示也不受影响
  * 列表与总览在同一快照内一致
  * 并发开窗/总览刷新不出现半截旧在途
"""
from __future__ import annotations

import concurrent.futures
import json
import sqlite3
import urllib.error
import urllib.request
import uuid
from pathlib import Path

DEFAULT_BASE = "http://127.0.0.1:11100/api"
DB_PATH = str(Path(__file__).resolve().parent / "data" / "curtainclock.db")


def call(method: str, path: str, body: dict | None = None, base: str = DEFAULT_BASE):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"detail": raw}
        return e.code, payload


def main() -> None:
    run = uuid.uuid4().hex[:8]

    st, dash0 = call("GET", "/dashboard")
    assert st == 200, dash0
    print("dashboard0", dash0)
    base_open = dash0["open_leases"]
    base_conf = dash0["conflict_count"]

    # ---- 1. 开窗 +1 ----
    st, open1 = call("POST", "/leases/open", {"session_code": "W-DIM-01"})
    assert st == 200, open1
    assert open1["open_leases"] == base_open + 1, open1
    lease_no = open1["lease_no"]
    print("open1", open1)

    st, dash1 = call("GET", "/dashboard")
    assert st == 200 and dash1["open_leases"] == base_open + 1, dash1
    assert dash1["open_leases"] == dash1["live_sessions"], dash1
    print("dashboard1", dash1)

    # ---- 2. 冲突加计（同算力槽时段，另一个执行器）----
    dup = f"W-DUP-{run}"
    st, created = call(
        "POST",
        "/sessions",
        {
            "code": dup,
            "title": "冲突试窗",
            "subject": "ETL",
            "room_code": "S-ETL-01",
            "teacher_code": "E-PIPE-02",
            "day": "2026-11-20",
            "start_min": 540,
            "end_min": 630,
        },
    )
    assert st == 200, created
    st, conflict = call("POST", "/leases/open", {"session_code": dup})
    assert st == 409, conflict
    print("conflict", conflict)

    st, dash2 = call("GET", "/dashboard")
    assert st == 200 and dash2["conflict_count"] >= base_conf + 1, dash2
    assert dash2["open_leases"] == base_open + 1, dash2
    assert dash2["open_leases"] == dash2["live_sessions"], dash2
    print("dashboard2", dash2)

    # 冲突页列表与总览同源
    st, conf_list = call("GET", "/conflicts")
    assert st == 200 and conf_list["conflict_count"] == dash2["conflict_count"], conf_list
    assert any(x["session_code"] == dup for x in conf_list["items"]), conf_list
    print("conflicts_list", conf_list["conflict_count"], len(conf_list["items"]))

    # ---- 3. 关窗 -1 ----
    st, closed = call("POST", "/leases/close", {"lease_no": lease_no})
    assert st == 200 and closed["open_leases"] == base_open, closed
    print("close", closed)

    # ---- 4. 列表与总览一致 ----
    st, dash3 = call("GET", "/dashboard")
    st2, leases = call("GET", "/leases")
    assert st == 200 and st2 == 200, (dash3, leases)
    open_in_list = sum(1 for x in leases["items"] if x["status"] == "open")
    assert open_in_list == dash3["open_leases"] == leases["open_leases"], (dash3, leases)
    assert leases["conflict_count"] == dash3["conflict_count"], (dash3, leases)
    print("consistent", dash3["open_leases"], open_in_list)

    # ---- 5. 直接写水位被禁止 / 不影响展示 ----
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DROP TABLE IF EXISTS watermarks")
        conn.commit()
        try:
            conn.execute(
                "INSERT INTO watermarks(key, value, updated_at) VALUES('open_leases', 999, 'x')"
            )
            conn.commit()
            raise AssertionError("水位表仍可写：写路径臂未禁止")
        except sqlite3.OperationalError as e:
            print("watermarks_write_blocked:", e)
        # 聚合臂：即便有人手工建表写假值，展示也只认聚合
        conn.execute(
            "CREATE TABLE IF NOT EXISTS watermarks (key TEXT PRIMARY KEY, value INTEGER NOT NULL, updated_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO watermarks(key, value, updated_at) VALUES('open_leases', 999, 'x') "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
        )
        conn.commit()
    finally:
        conn.close()
    st, dash4 = call("GET", "/dashboard")
    assert st == 200 and dash4["open_leases"] == dash3["open_leases"], dash4
    assert dash4["conflict_count"] == dash3["conflict_count"], dash4
    print("fake_watermark_ignored", dash4["open_leases"], dash4["conflict_count"])

    # ---- 6. 并发开窗 + 总览刷新：不出现半截 ----
    cc_codes = []
    for i in range(5):
        code = f"W-CC-{run}-{i}"
        st, created = call(
            "POST",
            "/sessions",
            {
                "code": code,
                "title": "并发试窗",
                "subject": "ETL",
                "room_code": "S-ETL-01",
                "teacher_code": "E-PIPE-01",
                "day": f"2026-12-{i + 1:02d}",  # 不同日期，互不重叠
                "start_min": 540,
                "end_min": 630,
            },
        )
        assert st == 200, created
        cc_codes.append(code)

    def open_and_close(code: str) -> None:
        st, r = call("POST", "/leases/open", {"session_code": code})
        assert st == 200, r
        st, r2 = call("POST", "/leases/close", {"lease_no": r["lease_no"]})
        assert st == 200, r2

    def poll() -> None:
        for _ in range(20):
            st, d = call("GET", "/dashboard")
            assert st == 200, d
            assert d["open_leases"] == d["live_sessions"], d

    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as ex:
        futures = [ex.submit(open_and_close, c) for c in cc_codes]
        futures += [ex.submit(poll) for _ in range(2)]
        for f in futures:
            f.result()

    st, dash5 = call("GET", "/dashboard")
    assert st == 200 and dash5["open_leases"] == base_open, dash5

    # 清理手工假表（重启 API 时 init_db 也会删除），避免污染后续运行
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DROP TABLE IF EXISTS watermarks")
        conn.commit()
    finally:
        conn.close()
    print("concurrent_ok", dash5)
    print("SMOKE_OK")


if __name__ == "__main__":
    main()
