"""Permisiuni pe roluri: pagini, dry_run si matricea completa utilizator x actiune."""
import pytest

from tests.conftest import ANDREI, ELENA, ION, MARIA, MIHAI, RADU, TEACHER, child_of

ALL_USERS = [MARIA, ION, ELENA, ANDREI, TEACHER, MIHAI, RADU]
ROLE = {MARIA: "parent", ION: "parent", ELENA: "parent", ANDREI: "parent",
        TEACHER: "teacher", MIHAI: "driver", RADU: "driver"}


# ---------- paginile fiecarui rol (verificate pe server cand ?u= e in link) ----------

PAGES = {"/parinte": "parent", "/sofer": "driver", "/profesor": "teacher"}


@pytest.mark.parametrize("user", ALL_USERS)
@pytest.mark.parametrize("path", PAGES)
def test_role_page_only_for_its_role(client, user, path):
    r = client.get(f"{path}?u={user}")
    if ROLE[user] == PAGES[path]:
        assert r.status_code == 200
    else:
        assert r.status_code == 403
        assert "Acces interzis" in r.text


@pytest.mark.parametrize("path", PAGES)
def test_role_page_unknown_user_forbidden(client, path):
    assert client.get(f"{path}?u=nu_exista").status_code == 403


@pytest.mark.parametrize("path", PAGES)
def test_role_page_without_user_loads(client, path):
    # fara ?u=, pagina se incarca, iar verificarea o face browserul dupa utilizatorul salvat
    assert client.get(path).status_code == 200


def test_forbidden_page_escapes_name(client):
    r = client.get(f"/profesor?u={MARIA}")
    assert "Maria Popescu" in r.text and "<script" not in r.text


@pytest.mark.parametrize("user", ALL_USERS)
def test_permissions_page_open_to_everyone(client, user):
    assert client.get(f"/permisiuni?u={user}").status_code == 200


# ---------- dry_run: verifica permisiunea fara sa salveze ----------

def test_dry_run_scan_allowed_saves_nothing(client):
    r = client.post("/api/scans?dry_run=true", json={"user_id": MIHAI, "type": "BUS_BOARD", "bracelet_uid": "NFC-1001"})
    assert r.status_code == 200 and r.json() == {"allowed": True, "dry_run": True}
    assert child_of(client, MARIA, "c_ana")["events"] == []


def test_dry_run_scan_wrong_role_forbidden(client):
    r = client.post("/api/scans?dry_run=true", json={"user_id": TEACHER, "type": "BUS_BOARD", "bracelet_uid": "NFC-1001"})
    assert r.status_code == 403


def test_dry_run_scan_unknown_bracelet_404(client):
    r = client.post("/api/scans?dry_run=true", json={"user_id": MIHAI, "type": "BUS_BOARD", "bracelet_uid": "NFC-0000"})
    assert r.status_code == 404


def test_dry_run_confirmation_allowed_saves_nothing(client):
    r = client.put("/api/children/c_ana/confirmation?dry_run=true", json={"user_id": MARIA, "status": "confirmed"})
    assert r.status_code == 200 and r.json()["dry_run"] is True
    assert child_of(client, MARIA, "c_ana")["confirmation"] is None


def test_dry_run_confirmation_other_parent_forbidden(client):
    r = client.put("/api/children/c_ana/confirmation?dry_run=true", json={"user_id": ION, "status": "confirmed"})
    assert r.status_code == 403


def test_dry_run_ignores_state_rules(client):
    # dry_run raspunde doar la "ai voie?", nu la "e momentul potrivit?" (plecare fara sosire -> tot 200)
    r = client.post("/api/scans?dry_run=true", json={"user_id": TEACHER, "type": "DEPARTURE", "bracelet_uid": "NFC-1001"})
    assert r.status_code == 200


# ---------- matricea completa: fiecare utilizator x fiecare actiune ----------

def _actions(c, user):
    return {
        "confirm_ana": c.put("/api/children/c_ana/confirmation?dry_run=true",
                             json={"user_id": user, "status": "confirmed"}).status_code,
        "confirm_sofia": c.put("/api/children/c_sofia/confirmation?dry_run=true",
                               json={"user_id": user, "status": "confirmed"}).status_code,
        "history_ana": c.get(f"/api/children/c_ana/history?user_id={user}").status_code,
        "board": c.post("/api/scans?dry_run=true",
                        json={"user_id": user, "type": "BUS_BOARD", "bracelet_uid": "NFC-1001"}).status_code,
        "arrive": c.post("/api/scans?dry_run=true",
                         json={"user_id": user, "type": "AFTERSCHOOL_ARRIVE", "bracelet_uid": "NFC-1001"}).status_code,
        "depart": c.post("/api/scans?dry_run=true",
                         json={"user_id": user, "type": "DEPARTURE", "bracelet_uid": "NFC-1001"}).status_code,
    }


EXPECTED_ALLOWED = {
    MARIA: {"confirm_ana", "history_ana"},
    ION: set(),
    ELENA: {"confirm_sofia"},
    ANDREI: {"confirm_sofia"},
    TEACHER: {"arrive", "depart"},
    MIHAI: {"board"},
    RADU: {"board"},  # poate scana si un copil de pe alt traseu (primeste avertisment, nu refuz)
}


@pytest.mark.parametrize("user", ALL_USERS)
def test_permission_matrix(client, user):
    codes = _actions(client, user)
    allowed = {name for name, code in codes.items() if code == 200}
    refused = {name: code for name, code in codes.items() if code != 200}
    assert allowed == EXPECTED_ALLOWED[user]
    assert all(code == 403 for code in refused.values()), refused


@pytest.mark.parametrize("user", ALL_USERS)
def test_children_list_matches_role(client, user):
    ids = {c["id"] for c in client.get(f"/api/me/{user}/children").json()["children"]}
    expected = {
        MARIA: {"c_ana", "c_matei"}, ION: {"c_luca"}, ELENA: {"c_sofia", "c_david"},
        ANDREI: {"c_sofia", "c_david"}, MIHAI: {"c_ana", "c_matei", "c_luca"},
        RADU: {"c_sofia", "c_david"}, TEACHER: {"c_ana", "c_matei", "c_luca", "c_sofia", "c_david"},
    }[user]
    assert ids == expected
