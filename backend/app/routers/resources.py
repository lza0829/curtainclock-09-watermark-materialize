from __future__ import annotations

from fastapi import APIRouter

from app.db import connect

router = APIRouter(tags=["resources"])


@router.get("/rooms")
def list_rooms():
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT code, name, capacity, active FROM rooms ORDER BY code"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/teachers")
def list_teachers():
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT code, name, subject, active FROM teachers ORDER BY code"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
