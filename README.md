# Afterschool – prototip (FastAPI + PostgreSQL)

Trei interfețe, un singur backend:

| Pagină | Pentru | Ce face |
|---|---|---|
| `/parinte` | Părinte (telefon) | Confirmă „vine / nu vine”, vede starea copilului, linia de timp a zilei, alerte, istoric |
| `/sofer` | Șofer (telefon) | Vede doar copiii de pe traseul lui, scanează la urcare (sau „fără brățară”), contoare urcați / așteptați / lipsesc |
| `/profesor` | Profesor (laptop) | Scanează sosirea și plecarea (cu „cine l-a luat”), vede alertele „urcat, dar nesosit” |

Deschide http://localhost:8000 și alege utilizatorul (login-ul e simulat).

## Rulare pe Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

docker compose up -d
uvicorn app.main:app --reload
```

**Fără Docker?** Rulează pe SQLite, același cod:
```powershell
$env:DATABASE_URL="sqlite:///afterschool.db"; uvicorn app.main:app --reload
```

**Pentru demo cu alertă rapidă** (alerta după 1 minut, nu 30):
```powershell
$env:ALERT_MINUTES="1"; uvicorn app.main:app --reload
```

Pe telefon: telefonul și laptopul trebuie să fie în aceeași rețea Wi-Fi. Pornești cu
`uvicorn app.main:app --host 0.0.0.0` și deschizi pe telefon `http://<IP-ul laptopului>:8000`
(IP-ul îl afli cu `ipconfig`). Dacă nu se deschide, permite Python în Windows Firewall.

Swagger (documentația API): http://localhost:8000/docs

Tabelele se creează automat la pornire; datele de test (inclusiv 3 zile de istoric) se pun
dacă baza e goală. Reset: butonul „Reset date demo” sau `python -m app.seed`.

## Structura

```
app/
  main.py      endpoint-uri + reguli (roluri, ordinea scanărilor, alerte)
  models.py    cele 6 tabele (SQLModel)
  db.py        conexiunea (PostgreSQL sau SQLite)
  seed.py      date de test
  timeutil.py  ziua și ora în fusul României
static/
  index.html   alegerea utilizatorului
  parent.html  aplicația părintelui (mobil)
  driver.html  aplicația șoferului (mobil)
  teacher.html ecranul profesorului
  common.js, style.css
```

## Tabele (6 din schema completă)

`users`, `routes` (cu `driver_id`), `children` (cu `bracelet_uid` unic și `route_id`),
`parent_child` (N-N), `attendance_confirmations` (`UNIQUE child_id + date`),
`scan_events` (`UNIQUE child_id + date + type`, `method` NFC/MANUAL, `picked_up_by`).

Starea copilului nu se salvează: se calculează din scanările zilei
(Așteptat → În autobuz → La afterschool → Plecat acasă).

## API

| Metodă | Rută | Ce face |
|---|---|---|
| GET | `/api/users` | utilizatorii (pentru alegerea din prototip) |
| GET | `/api/me/{user_id}/children` | copiii vizibili pentru acel utilizator, cu starea de azi |
| GET | `/api/children/{id}/history?user_id=` | istoricul ultimelor zile (doar pentru părinții copilului) |
| PUT | `/api/children/{id}/confirmation` | `{user_id, status: confirmed\|declined}` |
| POST | `/api/scans` | `{user_id, type, bracelet_uid}` sau `{user_id, type, child_id}` (manual), opțional `picked_up_by` |
| POST | `/api/dev/reset` | refacere date de test |

## Reguli implementate

- Părintele vede și confirmă doar pentru copiii lui; nu poate anula după ce copilul a fost scanat.
- Șoferul face doar „urcare”; profesorul face „sosire” și „plecare”.
- Plecarea cere sosire. Scanarea dublă e blocată de baza de date (`UNIQUE`), chiar și la două scanări simultane.
- Avertismente (scanarea se salvează, dar apare mesaj): copil neconfirmat, copil anunțat că nu vine, copil care nu e pe traseul șoferului.
- Alertă „urcat, dar nesosit” după `ALERT_MINUTES` (implicit 30), vizibilă la profesor și la părinte.

## Simplificări intenționate

Login simulat (alegere din listă) · fără notificări push (reîmprospătare la 5 s) · NFC simulat
(cod sau buton) · fără lucru offline · fără curse zilnice / panou de administrare.

## Scenariu de demo (2–3 minute)

1. **Maria (părinte)** → „✔ Da, vine” pentru Ana.
2. **Mihai (șofer)** → vede doar Traseul 1; scanează `NFC-1001`; pentru Matei apasă „Fără brățară”.
3. **Maria** → Ana „În autobuz”, cu ora; Matei apare cu eticheta „manual”.
4. Cu `ALERT_MINUTES=1`, după un minut **Prof. Andreea** vede rândurile roșii „urcat, nesosit”.
5. **Prof. Andreea** → „Sosire”, apoi „Plecare” → „Bunica Ioana”.
6. **Maria** → „Plecat acasă cu Bunica Ioana” și istoricul ultimelor zile.
