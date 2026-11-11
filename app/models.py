"""Tabelele prototipului (6 din schema completa).

Simplificari: bratara e un camp in children (nu tabel separat),
un copil are un singur traseu (route_id), fara tabelele trips / notifications.
"""
from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: str = Field(primary_key=True)
    name: str
    role: str  # parent | teacher | driver


class Route(SQLModel, table=True):
    __tablename__ = "routes"
    id: str = Field(primary_key=True)
    name: str
    driver_id: Optional[str] = Field(default=None, foreign_key="users.id")


class Child(SQLModel, table=True):
    __tablename__ = "children"
    id: str = Field(primary_key=True)
    first_name: str
    last_name: str
    bracelet_uid: str = Field(unique=True, index=True)
    route_id: Optional[str] = Field(default=None, foreign_key="routes.id")


class ParentChild(SQLModel, table=True):
    """Relatia N-N parinti <-> copii."""
    __tablename__ = "parent_child"
    parent_id: str = Field(foreign_key="users.id", primary_key=True)
    child_id: str = Field(foreign_key="children.id", primary_key=True)
    relationship: str = "parinte"


class AttendanceConfirmation(SQLModel, table=True):
    __tablename__ = "attendance_confirmations"
    __table_args__ = (UniqueConstraint("child_id", "date"),)  # o confirmare pe copil pe zi
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: str = Field(foreign_key="children.id", index=True)
    date: date
    status: str  # confirmed | declined
    confirmed_by: str = Field(foreign_key="users.id")
    updated_at: datetime


class ScanEvent(SQLModel, table=True):
    __tablename__ = "scan_events"
    # regula pusa in baza de date: o singura scanare de fiecare tip pe zi
    __table_args__ = (UniqueConstraint("child_id", "date", "type"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: str = Field(foreign_key="children.id", index=True)
    date: date
    type: str  # BUS_BOARD | AFTERSCHOOL_ARRIVE | DEPARTURE
    method: str = "NFC"  # NFC | MANUAL
    scanned_by: str = Field(foreign_key="users.id")
    scanned_at: datetime
    picked_up_by: Optional[str] = None  # doar la DEPARTURE
