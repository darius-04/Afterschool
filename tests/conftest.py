"""Configurare teste.

Implicit testele ruleaza pe o baza SQLite temporara (nu ating baza ta de dezvoltare).
Pe PostgreSQL:  TEST_DATABASE_URL=postgresql+psycopg://afterschool:afterschool@localhost:5432/afterschool_test
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest

_tmp = os.path.join(tempfile.gettempdir(), "afterschool_test.db")
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", f"sqlite:///{_tmp}")
os.environ.setdefault("ALERT_MINUTES", "30")

from fastapi.testclient import TestClient  # noqa: E402

import app.main as main  # noqa: E402
from app.timeutil import TZ  # noqa: E402

IS_POSTGRES = os.environ["DATABASE_URL"].startswith("postgresql")

# utilizatori din datele de test
MARIA, ION, ELENA, ANDREI = "u_parent_maria", "u_parent_ion", "u_parent_elena", "u_parent_andrei"
TEACHER, MIHAI, RADU = "u_teacher_andreea", "u_driver_mihai", "u_driver_radu"


@pytest.fixture(scope="session")
def _app_client():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def client(_app_client):
    """Fiecare test porneste de la datele de test curate."""
    assert _app_client.post("/api/dev/reset").status_code == 200
    return _app_client


class Clock:
    """Ceas controlabil: muta 'acum' inainte sau la alta zi."""

    def __init__(self, monkeypatch, start: datetime):
        self.current = start
        monkeypatch.setattr(main, "now", lambda: self.current)
        monkeypatch.setattr(main, "today", lambda: self.current.date())

    def advance(self, **kw):
        self.current += timedelta(**kw)


@pytest.fixture
def clock(monkeypatch):
    # o zi lucratoare la 12:30, ora Romaniei
    return Clock(monkeypatch, datetime.now(TZ).replace(hour=12, minute=30, second=0, microsecond=0))


# ---------- helpers ----------

def confirm(c, user, child, status="confirmed"):
    return c.put(f"/api/children/{child}/confirmation", json={"user_id": user, "status": status})


def scan(c, user, type_, uid=None, child=None, picked_up_by=None):
    body = {"user_id": user, "type": type_}
    if uid is not None:
        body["bracelet_uid"] = uid
    if child is not None:
        body["child_id"] = child
    if picked_up_by is not None:
        body["picked_up_by"] = picked_up_by
    return c.post("/api/scans", json=body)


def child_of(c, user, child_id):
    data = c.get(f"/api/me/{user}/children").json()
    return next(x for x in data["children"] if x["id"] == child_id)
