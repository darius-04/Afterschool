"""Cazuri-limita pentru prototipul afterschool.

Rulare:  pytest -v
"""
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.conftest import (ANDREI, ELENA, ION, IS_POSTGRES, MARIA, MIHAI, RADU, TEACHER, child_of, confirm,
                            scan)


# =====================================================================
# 1. Cine vede ce (roluri si acces)
# =====================================================================

class TestVisibility:
    def test_parent_sees_only_own_children(self, client):
        names = {c["id"] for c in client.get(f"/api/me/{ION}/children").json()["children"]}
        assert names == {"c_luca"}

    def test_child_with_two_parents_visible_to_both(self, client):
        for parent in (ELENA, ANDREI):
            ids = {c["id"] for c in client.get(f"/api/me/{parent}/children").json()["children"]}
            assert ids == {"c_sofia", "c_david"}

    def test_driver_sees_only_own_route(self, client):
        mihai = {c["id"] for c in client.get(f"/api/me/{MIHAI}/children").json()["children"]}
        radu = {c["id"] for c in client.get(f"/api/me/{RADU}/children").json()["children"]}
        assert mihai == {"c_ana", "c_matei", "c_luca"}
        assert radu == {"c_sofia", "c_david"}
        assert not mihai & radu

    def test_teacher_sees_all_children(self, client):
        assert len(client.get(f"/api/me/{TEACHER}/children").json()["children"]) == 5

    def test_unknown_user_gets_404(self, client):
        assert client.get("/api/me/nu_exista/children").status_code == 404

    def test_history_only_for_own_parent(self, client):
        assert client.get(f"/api/children/c_ana/history?user_id={MARIA}").status_code == 200
        assert client.get(f"/api/children/c_ana/history?user_id={ION}").status_code == 403
        assert client.get(f"/api/children/c_ana/history?user_id={TEACHER}").status_code == 403

    def test_history_unknown_child(self, client):
        assert client.get(f"/api/children/nu_exista/history?user_id={MARIA}").status_code == 404

    def test_history_requires_user(self, client):
        assert client.get("/api/children/c_ana/history").status_code == 422

    def test_history_excludes_today(self, client, clock):
        confirm(client, MARIA, "c_ana")
        days = client.get(f"/api/children/c_ana/history?user_id={MARIA}").json()
        assert all(d["date"] != clock.current.date().isoformat() for d in days)

    @pytest.mark.parametrize("days", [0, -5, 100000])
    def test_history_days_out_of_range_rejected(self, client, days):
        # un 'days' urias ar face mii de interogari intr-o singura cerere
        assert client.get(f"/api/children/c_ana/history?user_id={MARIA}&days={days}").status_code == 422


# =====================================================================
# 2. Confirmarea participarii
# =====================================================================

class TestConfirmation:
    def test_other_parent_cannot_confirm(self, client):
        assert confirm(client, ION, "c_ana").status_code == 403

    @pytest.mark.parametrize("user", [TEACHER, MIHAI])
    def test_staff_cannot_confirm(self, client, user):
        assert confirm(client, user, "c_ana").status_code == 403

    def test_unknown_child(self, client):
        assert confirm(client, MARIA, "nu_exista").status_code == 404

    def test_invalid_status_rejected(self, client):
        assert confirm(client, MARIA, "c_ana", status="poate").status_code == 422

    def test_confirm_twice_is_idempotent(self, client):
        assert confirm(client, MARIA, "c_ana").status_code == 200
        assert confirm(client, MARIA, "c_ana").status_code == 200
        assert child_of(client, MARIA, "c_ana")["confirmation"] == "confirmed"

    def test_change_mind_before_scan(self, client):
        confirm(client, MARIA, "c_ana")
        assert confirm(client, MARIA, "c_ana", "declined").status_code == 200
        assert child_of(client, MARIA, "c_ana")["confirmation"] == "declined"

    def test_cannot_decline_after_scan(self, client):
        confirm(client, MARIA, "c_ana")
        scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001")
        assert confirm(client, MARIA, "c_ana", "declined").status_code == 409

    def test_can_confirm_after_scan(self, client):
        # copilul a urcat fara confirmare; parintele confirma ulterior: e permis
        scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001")
        assert confirm(client, MARIA, "c_ana").status_code == 200

    def test_second_parent_overrides_first(self, client):
        confirm(client, ELENA, "c_sofia", "confirmed")
        confirm(client, ANDREI, "c_sofia", "declined")
        assert child_of(client, ELENA, "c_sofia")["confirmation"] == "declined"


# =====================================================================
# 3. Scanari: roluri, ordine, duplicate
# =====================================================================

class TestScanRules:
    def test_driver_cannot_do_arrival_or_departure(self, client):
        assert scan(client, MIHAI, "AFTERSCHOOL_ARRIVE", uid="NFC-1001").status_code == 403
        assert scan(client, MIHAI, "DEPARTURE", uid="NFC-1001").status_code == 403

    def test_teacher_cannot_do_bus_board(self, client):
        assert scan(client, TEACHER, "BUS_BOARD", uid="NFC-1001").status_code == 403

    def test_parent_cannot_scan(self, client):
        assert scan(client, MARIA, "BUS_BOARD", uid="NFC-1001").status_code == 403

    def test_invalid_scan_type(self, client):
        assert scan(client, MIHAI, "TELEPORT", uid="NFC-1001").status_code == 422

    def test_unknown_bracelet(self, client):
        assert scan(client, MIHAI, "BUS_BOARD", uid="NFC-9999").status_code == 404

    @pytest.mark.parametrize("uid", ["nfc-1001", "  NFC-1001  ", "Nfc-1001"])
    def test_bracelet_code_normalized(self, client, uid):
        assert scan(client, MIHAI, "BUS_BOARD", uid=uid).status_code == 200

    def test_no_bracelet_and_no_child(self, client):
        assert scan(client, MIHAI, "BUS_BOARD").status_code == 422

    def test_empty_bracelet_code(self, client):
        assert scan(client, MIHAI, "BUS_BOARD", uid="   ").status_code in (404, 422)

    def test_manual_unknown_child(self, client):
        assert scan(client, MIHAI, "BUS_BOARD", child="nu_exista").status_code == 404

    def test_manual_scan_is_marked(self, client):
        r = scan(client, MIHAI, "BUS_BOARD", child="c_matei")
        assert r.status_code == 200 and r.json()["method"] == "MANUAL"
        assert child_of(client, MARIA, "c_matei")["events"][0]["method"] == "MANUAL"

    def test_double_scan_rejected(self, client):
        assert scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001").status_code == 200
        assert scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001").status_code == 409

    def test_manual_then_nfc_is_still_duplicate(self, client):
        scan(client, MIHAI, "BUS_BOARD", child="c_ana")
        assert scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001").status_code == 409

    def test_departure_requires_arrival(self, client):
        assert scan(client, TEACHER, "DEPARTURE", uid="NFC-1001").status_code == 409

    def test_arrival_without_bus_allowed(self, client):
        # copil adus direct de parinte
        assert scan(client, TEACHER, "AFTERSCHOOL_ARRIVE", uid="NFC-1001").status_code == 200
        assert child_of(client, MARIA, "c_ana")["state"] == "AT_AFTERSCHOOL"

    def test_bus_board_after_arrival_rejected(self, client):
        scan(client, TEACHER, "AFTERSCHOOL_ARRIVE", uid="NFC-1001")
        assert scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001").status_code == 409

    def test_double_departure_rejected(self, client):
        scan(client, TEACHER, "AFTERSCHOOL_ARRIVE", uid="NFC-1001")
        assert scan(client, TEACHER, "DEPARTURE", uid="NFC-1001").status_code == 200
        assert scan(client, TEACHER, "DEPARTURE", uid="NFC-1001").status_code == 409

    def test_full_day_state_progression(self, client):
        states = [child_of(client, MARIA, "c_ana")["state"]]
        scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001")
        states.append(child_of(client, MARIA, "c_ana")["state"])
        scan(client, TEACHER, "AFTERSCHOOL_ARRIVE", uid="NFC-1001")
        states.append(child_of(client, MARIA, "c_ana")["state"])
        scan(client, TEACHER, "DEPARTURE", uid="NFC-1001", picked_up_by="Bunica Ioana")
        states.append(child_of(client, MARIA, "c_ana")["state"])
        assert states == ["WAITING", "ON_BUS", "AT_AFTERSCHOOL", "LEFT"]

    def test_state_correct_when_scans_in_same_second(self, client, clock):
        scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001")
        scan(client, TEACHER, "AFTERSCHOOL_ARRIVE", uid="NFC-1001")
        scan(client, TEACHER, "DEPARTURE", uid="NFC-1001")
        c = child_of(client, MARIA, "c_ana")
        assert c["state"] == "LEFT"
        assert [e["type"] for e in c["events"]] == ["BUS_BOARD", "AFTERSCHOOL_ARRIVE", "DEPARTURE"]


# =====================================================================
# 4. Avertismente si persoana care ia copilul
# =====================================================================

class TestWarningsAndPickup:
    def test_warning_when_unconfirmed(self, client):
        w = scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001").json()["warnings"]
        assert any("nu a confirmat" in x for x in w)

    def test_no_warning_when_confirmed_on_own_route(self, client):
        confirm(client, MARIA, "c_ana")
        assert scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001").json()["warnings"] == []

    def test_warning_when_declined(self, client):
        confirm(client, ION, "c_luca", "declined")
        w = scan(client, MIHAI, "BUS_BOARD", uid="NFC-1003").json()["warnings"]
        assert any("NU vine" in x for x in w)

    def test_warning_when_other_route(self, client):
        w = scan(client, MIHAI, "BUS_BOARD", uid="NFC-1004").json()["warnings"]
        assert any("traseul tău" in x for x in w)

    def test_picked_up_by_saved_on_departure(self, client):
        scan(client, TEACHER, "AFTERSCHOOL_ARRIVE", uid="NFC-1001")
        scan(client, TEACHER, "DEPARTURE", uid="NFC-1001", picked_up_by="  Bunica Ioana ")
        assert child_of(client, MARIA, "c_ana")["events"][-1]["picked_up_by"] == "Bunica Ioana"

    def test_picked_up_by_ignored_on_other_steps(self, client):
        scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001", picked_up_by="Cineva")
        assert child_of(client, MARIA, "c_ana")["events"][0]["picked_up_by"] is None

    def test_departure_without_pickup_person_warns(self, client):
        scan(client, TEACHER, "AFTERSCHOOL_ARRIVE", uid="NFC-1001")
        r = scan(client, TEACHER, "DEPARTURE", uid="NFC-1001", picked_up_by="")
        assert r.status_code == 200
        assert any("cine a luat" in x.lower() for x in r.json()["warnings"])

    def test_picked_up_by_too_long_rejected(self, client):
        scan(client, TEACHER, "AFTERSCHOOL_ARRIVE", uid="NFC-1001")
        assert scan(client, TEACHER, "DEPARTURE", uid="NFC-1001", picked_up_by="x" * 500).status_code == 422

    def test_html_in_pickup_name_is_stored_as_text(self, client):
        # interfata il afiseaza escapat; API-ul il pastreaza ca text
        scan(client, TEACHER, "AFTERSCHOOL_ARRIVE", uid="NFC-1001")
        scan(client, TEACHER, "DEPARTURE", uid="NFC-1001", picked_up_by="<script>alert(1)</script>")
        assert child_of(client, MARIA, "c_ana")["events"][-1]["picked_up_by"] == "<script>alert(1)</script>"


# =====================================================================
# 5. Ora si ziua (alerta, trecerea la ziua urmatoare)
# =====================================================================

class TestTimeAndAlerts:
    def test_no_alert_before_threshold(self, client, clock):
        scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001")
        clock.advance(minutes=29)
        assert child_of(client, TEACHER, "c_ana")["alert"] is None

    def test_alert_after_threshold(self, client, clock):
        scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001")
        clock.advance(minutes=31)
        assert "31 min" in child_of(client, TEACHER, "c_ana")["alert"]

    def test_alert_visible_to_parent(self, client, clock):
        scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001")
        clock.advance(minutes=45)
        assert child_of(client, MARIA, "c_ana")["alert"]

    def test_alert_clears_after_arrival(self, client, clock):
        scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001")
        clock.advance(minutes=45)
        scan(client, TEACHER, "AFTERSCHOOL_ARRIVE", uid="NFC-1001")
        assert child_of(client, TEACHER, "c_ana")["alert"] is None

    def test_new_day_starts_clean(self, client, clock):
        confirm(client, MARIA, "c_ana")
        scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001")
        clock.advance(days=1)
        c = child_of(client, MARIA, "c_ana")
        assert c["state"] == "WAITING" and c["confirmation"] is None and c["events"] == []
        assert scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001").status_code == 200

    def test_yesterday_unfinished_trip_no_alert_today(self, client, clock):
        scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001")
        clock.advance(days=1)
        assert child_of(client, TEACHER, "c_ana")["alert"] is None

    def test_scan_just_before_midnight_counts_for_that_day(self, client, clock):
        clock.current = clock.current.replace(hour=23, minute=59, second=59)
        scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001")
        clock.advance(seconds=2)  # trece de miezul noptii
        assert child_of(client, MARIA, "c_ana")["state"] == "WAITING"

    def test_decline_allowed_again_next_day(self, client, clock):
        scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001")
        clock.advance(days=1)
        assert confirm(client, MARIA, "c_ana", "declined").status_code == 200


# =====================================================================
# 6. Cereri simultane (doar pe PostgreSQL)
# =====================================================================

@pytest.mark.skipif(not IS_POSTGRES, reason="concurenta reala doar pe PostgreSQL")
class TestConcurrency:
    def test_simultaneous_same_scan_saved_once(self, client):
        with ThreadPoolExecutor(8) as pool:
            codes = list(pool.map(lambda _: scan(client, MIHAI, "BUS_BOARD", uid="NFC-1001").status_code,
                                  range(8)))
        assert codes.count(200) == 1
        assert codes.count(409) == 7
        assert len(child_of(client, MARIA, "c_ana")["events"]) == 1

    def test_simultaneous_first_confirmations_no_server_error(self, client):
        # doi parinti (sau doua tap-uri) confirma in acelasi moment, prima confirmare a zilei
        # cursa nu apare la fiecare rulare, asa ca o incercam de mai multe ori
        users = [ELENA, ANDREI] * 4
        for _ in range(10):
            client.post("/api/dev/reset")
            with ThreadPoolExecutor(8) as pool:
                codes = list(pool.map(lambda u: confirm(client, u, "c_sofia").status_code, users))
            assert all(code == 200 for code in codes), codes


# =====================================================================
# 7. Endpoint-ul de reset (doar pentru demo)
# =====================================================================

def test_reset_can_be_disabled(client, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "ENABLE_DEV_RESET", False)
    assert client.post("/api/dev/reset").status_code == 404
