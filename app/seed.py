"""Date de test. Reset manual: python -m app.seed"""
from datetime import datetime, time, timedelta

from sqlmodel import Session, delete, select

from app.db import create_tables, engine
from app.models import AttendanceConfirmation, Child, ParentChild, Route, ScanEvent, User
from app.timeutil import TZ, today

USERS = [
    ("u_parent_maria", "Maria Popescu", "parent"),
    ("u_parent_ion", "Ion Ionescu", "parent"),
    ("u_parent_elena", "Elena Georgescu", "parent"),
    ("u_parent_andrei", "Andrei Georgescu", "parent"),
    ("u_teacher_andreea", "Prof. Andreea Dumitru", "teacher"),
    ("u_driver_mihai", "Mihai Stan", "driver"),
    ("u_driver_radu", "Radu Marin", "driver"),
]
ROUTES = [
    ("r1", "Traseu 1 – Școala nr. 5", "u_driver_mihai"),
    ("r2", "Traseu 2 – Școala nr. 12", "u_driver_radu"),
]
CHILDREN = [
    ("c_ana", "Ana", "Popescu", "NFC-1001", "r1"),
    ("c_matei", "Matei", "Popescu", "NFC-1002", "r1"),
    ("c_luca", "Luca", "Ionescu", "NFC-1003", "r1"),
    ("c_sofia", "Sofia", "Georgescu", "NFC-1004", "r2"),
    ("c_david", "David", "Georgescu", "NFC-1005", "r2"),
]
PARENT_CHILD = [
    ("u_parent_maria", "c_ana", "mamă"),
    ("u_parent_maria", "c_matei", "mamă"),
    ("u_parent_ion", "c_luca", "tată"),
    # Sofia si David au doi parinti in sistem (exemplu de relatie N-N)
    ("u_parent_elena", "c_sofia", "mamă"),
    ("u_parent_elena", "c_david", "mamă"),
    ("u_parent_andrei", "c_sofia", "tată"),
    ("u_parent_andrei", "c_david", "tată"),
]


def _past_days(session: Session) -> None:
    """Istoric pentru ultimele 3 zile lucratoare, ca parintele sa aiba ce vedea."""
    day = today()
    added = 0
    while added < 3:
        day -= timedelta(days=1)
        if day.weekday() >= 5:
            continue
        added += 1
        at = lambda h, m: datetime.combine(day, time(h, m), tzinfo=TZ)  # noqa: E731
        for cid, driver in (("c_ana", "u_driver_mihai"), ("c_sofia", "u_driver_radu")):
            parent = "u_parent_maria" if cid == "c_ana" else "u_parent_elena"
            session.add(AttendanceConfirmation(child_id=cid, date=day, status="confirmed",
                                               confirmed_by=parent, updated_at=at(7, 30)))
            session.add(ScanEvent(child_id=cid, date=day, type="BUS_BOARD", scanned_by=driver,
                                  scanned_at=at(12, 40)))
            session.add(ScanEvent(child_id=cid, date=day, type="AFTERSCHOOL_ARRIVE",
                                  scanned_by="u_teacher_andreea", scanned_at=at(13, 5)))
            session.add(ScanEvent(child_id=cid, date=day, type="DEPARTURE",
                                  scanned_by="u_teacher_andreea", scanned_at=at(17, 30),
                                  picked_up_by="Maria Popescu (mamă)" if cid == "c_ana" else "Bunica Ioana"))
        session.add(AttendanceConfirmation(child_id="c_matei", date=day, status="declined",
                                           confirmed_by="u_parent_maria", updated_at=at(7, 0)))


def seed(force: bool = False) -> bool:
    create_tables()
    with Session(engine) as session:
        if not force and session.exec(select(User)).first():
            return False
        for model in (ScanEvent, AttendanceConfirmation, ParentChild, Child, Route, User):
            session.exec(delete(model))
        session.commit()
        session.add_all([User(id=i, name=n, role=r) for i, n, r in USERS])
        session.commit()
        session.add_all([Route(id=i, name=n, driver_id=d) for i, n, d in ROUTES])
        session.commit()
        session.add_all([Child(id=i, first_name=f, last_name=l, bracelet_uid=b, route_id=r)
                         for i, f, l, b, r in CHILDREN])
        session.commit()
        session.add_all([ParentChild(parent_id=p, child_id=c, relationship=r) for p, c, r in PARENT_CHILD])
        _past_days(session)
        session.commit()
    return True


if __name__ == "__main__":
    seed(force=True)
    print("Seed OK")
