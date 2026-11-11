import os
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.db import create_tables, get_session
from app.models import AttendanceConfirmation, Child, ParentChild, Route, ScanEvent, User
from app.seed import seed
from app.timeutil import local, now, today

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
ALERT_MINUTES = int(os.getenv("ALERT_MINUTES", "30"))  # "urcat, dar nesosit" dupa X minute
# in productie: ENABLE_DEV_RESET=0 (endpoint-ul de reset dispare, iar datele de test nu se mai pun automat)
ENABLE_DEV_RESET = os.getenv("ENABLE_DEV_RESET", "1") == "1"

EventType = Literal["BUS_BOARD", "AFTERSCHOOL_ARRIVE", "DEPARTURE"]
ROLE_EVENTS = {"driver": {"BUS_BOARD"}, "teacher": {"AFTERSCHOOL_ARRIVE", "DEPARTURE"}}
STEP_ORDER = ["BUS_BOARD", "AFTERSCHOOL_ARRIVE", "DEPARTURE"]
STATE_BY_LAST_EVENT = {None: "WAITING", "BUS_BOARD": "ON_BUS",
                       "AFTERSCHOOL_ARRIVE": "AT_AFTERSCHOOL", "DEPARTURE": "LEFT"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    if ENABLE_DEV_RESET:
        seed()  # creeaza tabelele; populeaza doar daca baza e goala
    else:
        create_tables()
    yield


app = FastAPI(title="Afterschool – prototip (FastAPI + PostgreSQL)", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------- helpers ----------

def get_user(session: Session, user_id: str) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(404, "Utilizator inexistent")
    return user


def build_status(session: Session, children: list[Child], day: date) -> list[dict]:
    """Starea fiecarui copil pe ziua data. 3 query-uri in total, indiferent cati copii sunt."""
    if not children:
        return []
    ids = [c.id for c in children]
    routes = {r.id: r for r in session.exec(select(Route))}
    users = {u.id: u.name for u in session.exec(select(User))}
    confs = {c.child_id: c for c in session.exec(
        select(AttendanceConfirmation).where(col(AttendanceConfirmation.child_id).in_(ids),
                                             AttendanceConfirmation.date == day))}
    scans = defaultdict(list)
    for s in session.exec(select(ScanEvent).where(col(ScanEvent.child_id).in_(ids), ScanEvent.date == day)
                          .order_by(ScanEvent.scanned_at, ScanEvent.id)):
        scans[s.child_id].append(s)

    result = []
    for c in children:
        # starea = cel mai avansat pas facut azi (nu depinde de ordinea orelor)
        events = sorted(scans[c.id], key=lambda e: STEP_ORDER.index(e.type))
        last = events[-1] if events else None
        state = STATE_BY_LAST_EVENT[last.type if last else None]
        conf = confs.get(c.id)

        alert = None
        if state == "ON_BUS" and day == today():
            minutes = int((now() - local(last.scanned_at)).total_seconds() // 60)
            if minutes >= ALERT_MINUTES:
                alert = f"A urcat în autobuz acum {minutes} min și nu a fost scanat la sosire"

        route = routes.get(c.route_id)
        result.append({
            "id": c.id,
            "name": f"{c.first_name} {c.last_name}",
            "first_name": c.first_name,
            "bracelet_uid": c.bracelet_uid,
            "route": route.name if route else None,
            "confirmation": conf.status if conf else None,
            "confirmed_at": local(conf.updated_at).strftime("%H:%M") if conf else None,
            "state": state,
            "alert": alert,
            "events": [{"type": e.type, "time": local(e.scanned_at).strftime("%H:%M"), "method": e.method,
                        "by": users.get(e.scanned_by), "picked_up_by": e.picked_up_by} for e in events],
        })
    return result


# ---------- modele de intrare ----------

class ConfirmationIn(BaseModel):
    user_id: str
    status: Literal["confirmed", "declined"]


class ScanIn(BaseModel):
    user_id: str
    type: EventType
    bracelet_uid: Optional[str] = None  # scanare (simulata) a bratarii
    child_id: Optional[str] = None      # bifare manuala, cand bratara nu merge
    picked_up_by: Optional[str] = Field(default=None, max_length=100)  # la plecare: cine a luat copilul

    @field_validator("picked_up_by")
    @classmethod
    def _strip(cls, v):
        if v is None:
            return None
        return v.strip() or None


# ---------- pagini ----------

@app.get("/")
def page_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/parinte")
def page_parent():
    return FileResponse(STATIC_DIR / "parent.html")


@app.get("/sofer")
def page_driver():
    return FileResponse(STATIC_DIR / "driver.html")


@app.get("/profesor")
def page_teacher():
    return FileResponse(STATIC_DIR / "teacher.html")


# ---------- API ----------

@app.get("/api/users")
def list_users(session: Session = Depends(get_session)):
    return [{"id": u.id, "name": u.name, "role": u.role} for u in session.exec(select(User))]


@app.get("/api/me/{user_id}/children")
def my_children(user_id: str, session: Session = Depends(get_session)):
    """Fiecare rol vede doar ce il priveste:
    parinte -> copiii lui · sofer -> copiii de pe traseul lui · profesor -> toti copiii."""
    user = get_user(session, user_id)
    query = select(Child)
    route_names = []
    if user.role == "parent":
        query = query.join(ParentChild, ParentChild.child_id == Child.id).where(ParentChild.parent_id == user.id)
    elif user.role == "driver":
        my_routes = session.exec(select(Route).where(Route.driver_id == user.id)).all()
        route_names = [r.name for r in my_routes]
        query = query.where(col(Child.route_id).in_([r.id for r in my_routes]))
    children = session.exec(query.order_by(Child.route_id, Child.first_name)).all()
    return {"date": today().isoformat(), "routes": route_names, "alert_minutes": ALERT_MINUTES,
            "children": build_status(session, list(children), today())}


@app.get("/api/children/{child_id}/history")
def child_history(child_id: str, user_id: str, days: int = Query(7, ge=1, le=60),
                  session: Session = Depends(get_session)):
    """Istoricul ultimelor zile (fara azi). Doar pentru parintii copilului."""
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Copil inexistent")
    if not session.get(ParentChild, (user_id, child_id)):
        raise HTTPException(403, "Poți vedea doar istoricul copiilor tăi")
    out = []
    for i in range(1, days + 1):
        day = today() - timedelta(days=i)
        st = build_status(session, [child], day)[0]
        if st["confirmation"] or st["events"]:
            out.append({"date": day.isoformat(), **st})
    return out


@app.put("/api/children/{child_id}/confirmation")
def set_confirmation(child_id: str, body: ConfirmationIn, session: Session = Depends(get_session)):
    user = get_user(session, body.user_id)
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Copil inexistent")
    if user.role != "parent" or not session.get(ParentChild, (user.id, child_id)):
        raise HTTPException(403, "Doar părintele copilului poate confirma participarea")

    day = today()
    scanned = session.exec(select(ScanEvent).where(ScanEvent.child_id == child_id, ScanEvent.date == day)).first()
    if body.status == "declined" and scanned:
        raise HTTPException(409, "Copilul a fost deja scanat azi; nu mai poți anula participarea")

    conf = session.exec(select(AttendanceConfirmation).where(
        AttendanceConfirmation.child_id == child_id, AttendanceConfirmation.date == day)).first()
    if conf:
        conf.status, conf.confirmed_by, conf.updated_at = body.status, user.id, now()
        session.add(conf)
        session.commit()
    else:
        session.add(AttendanceConfirmation(child_id=child_id, date=day, status=body.status,
                                           confirmed_by=user.id, updated_at=now()))
        try:
            session.commit()
        except IntegrityError:
            # alta cerere a creat confirmarea zilei in acelasi moment -> o actualizam pe aceea
            session.rollback()
            conf = session.exec(select(AttendanceConfirmation).where(
                AttendanceConfirmation.child_id == child_id, AttendanceConfirmation.date == day)).one()
            conf.status, conf.confirmed_by, conf.updated_at = body.status, user.id, now()
            session.add(conf)
            session.commit()
    return build_status(session, [child], day)[0]


@app.post("/api/scans")
def scan(body: ScanIn, session: Session = Depends(get_session)):
    user = get_user(session, body.user_id)
    if body.type not in ROLE_EVENTS.get(user.role, set()):
        raise HTTPException(403, "Rolul tău nu poate face această scanare")

    if body.bracelet_uid:
        child = session.exec(select(Child).where(Child.bracelet_uid == body.bracelet_uid.strip().upper())).first()
        if not child:
            raise HTTPException(404, f"Nicio brățară cu codul {body.bracelet_uid}")
        method = "NFC"
    elif body.child_id:
        child = session.get(Child, body.child_id)
        if not child:
            raise HTTPException(404, "Copil inexistent")
        method = "MANUAL"
    else:
        raise HTTPException(422, "Trimite codul brățării sau copilul (bifare manuală)")

    day = today()
    done = {s.type for s in session.exec(select(ScanEvent).where(ScanEvent.child_id == child.id,
                                                                ScanEvent.date == day))}
    if body.type == "BUS_BOARD" and done - {"BUS_BOARD"}:
        raise HTTPException(409, f"{child.first_name} e deja la afterschool sau a plecat")
    if body.type == "DEPARTURE" and "AFTERSCHOOL_ARRIVE" not in done:
        raise HTTPException(409, f"{child.first_name} nu a fost scanat(ă) la sosirea la afterschool")

    session.add(ScanEvent(child_id=child.id, date=day, type=body.type, method=method, scanned_by=user.id,
                          scanned_at=now(),
                          picked_up_by=body.picked_up_by if body.type == "DEPARTURE" else None))
    try:
        session.commit()
    except IntegrityError:  # UNIQUE (child_id, date, type) -> scanare dubla, chiar si simultana
        session.rollback()
        raise HTTPException(409, f"{child.first_name} a fost deja scanat(ă) pentru acest pas azi")

    # avertismente: scanarea se salveaza, dar cel care scaneaza trebuie sa stie
    warnings = []
    conf = session.exec(select(AttendanceConfirmation).where(
        AttendanceConfirmation.child_id == child.id, AttendanceConfirmation.date == day)).first()
    if not conf:
        warnings.append("Părintele nu a confirmat participarea azi")
    elif conf.status == "declined":
        warnings.append("Atenție: părintele a anunțat că NU vine azi!")
    if body.type == "DEPARTURE" and not body.picked_up_by:
        warnings.append("Nu s-a notat cine a luat copilul")
    if user.role == "driver":
        route = session.get(Route, child.route_id) if child.route_id else None
        if not route or route.driver_id != user.id:
            warnings.append("Copilul nu e pe traseul tău")

    return {"child": build_status(session, [child], day)[0], "warnings": warnings, "method": method}


@app.post("/api/dev/reset")
def reset():
    """Doar pentru demo: reface datele de test (sterge confirmarile si scanarile de azi)."""
    if not ENABLE_DEV_RESET:
        raise HTTPException(404, "Not Found")
    seed(force=True)
    return {"ok": True}
