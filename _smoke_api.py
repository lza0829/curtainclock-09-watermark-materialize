# -*- coding: utf-8 -*-
"""0-1 API smoke against running server on 11100."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:11100/api"


def call(method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
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
    st, dash = call("GET", "/dashboard")
    assert st == 200, dash
    print("dashboard", dash)

    st, open1 = call("POST", "/leases/open", {"session_code": "S-MATH-01"})
    assert st == 200, open1
    print("open1", open1)

    # same room+slot different teacher -> conflict
    st, created = call(
        "POST",
        "/sessions",
        {
            "code": "S-MATH-DUP",
            "title": "冲突试课",
            "subject": "数学",
            "room_code": "R-101",
            "teacher_code": "T-CHEN",
            "day": "2026-11-20",
            "start_min": 540,
            "end_min": 630,
        },
    )
    assert st == 200, created
    st, conflict = call("POST", "/leases/open", {"session_code": "S-MATH-DUP"})
    assert st == 409, conflict
    print("conflict", conflict)

    st, closed = call("POST", "/leases/close", {"lease_no": open1["lease_no"]})
    assert st == 200, closed
    print("close", closed)

    st, dash2 = call("GET", "/dashboard")
    assert st == 200 and dash2["open_leases"] == 0, dash2
    assert dash2["conflict_count"] >= 1, dash2
    print("dashboard_after", dash2)
    print("SMOKE_OK")


if __name__ == "__main__":
    main()
