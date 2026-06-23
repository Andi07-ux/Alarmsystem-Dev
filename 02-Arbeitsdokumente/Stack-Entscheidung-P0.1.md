# Stack-Entscheidung (P0.1 / DTB-2)

> **Zweck:** Konsolidiertes, zitierbares Deliverable der **finalen Technologie-Stack-Wahl** des Backends (G2).
> Bündelt die über mehrere ADR-Einträge verteilte Entscheidung an **einer** Stelle und räumt die veralteten
> Vor-Stände (SQLite, HTTP-POST) auf. **Bewertungsrelevant** (Nachvollziehbarkeit techn. Entscheidungen).
> **Autor:** Lucas Vöhringer (Systemarchitekt) · **Stand:** 2026-06-23 · **Task:** DTB-2 / P0.1.
> **Detail-Begründungen (ADR-Format):** `Entscheidungslog-Lucas-Systemarchitektur.md` E-08/E-29/E-30/E-31;
> Architektur-Spec: `Backend-Konzept.md §6/§6a`. **Bei Konflikt gewinnen die E-xx-Einträge + dieses Blatt.**

---

## 1. Finaler Stack (gesetzt)

| Schicht | Wahl | Version (Repo) | Bezug |
|---|---|---|---|
| Sprache | **Python** | `>= 3.12` (`pyproject.toml`) | E-08 |
| Web-/API-Framework | **FastAPI** | `>= 0.115` | E-08 |
| Validierung/Schemas | **Pydantic** (mit FastAPI) | (FastAPI-Dep) | E-08 |
| ASGI-Server | **Uvicorn** `[standard]` | `>= 0.30` | E-08 |
| Persistenz-Abstraktion | **SQLAlchemy** + Repository-Pattern | `>= 2.0` | E-04, E-29 |
| Datenbank | **MySQL / MariaDB** (durchgängig, dev = prod) | MariaDB 11.8 (Pi) | **E-29 (GL-Vorgabe)** |
| DB-Treiber | **PyMySQL** | `>= 1.1` | E-29 |
| Migrationen | **Alembic** | `>= 1.13` | E-29 |
| DB-Bereitstellung (dev) | **Docker-Compose** (MariaDB) | `docker-compose.yml` | E-29 |
| Test / Lint | **pytest** · **ruff** | `pyproject.toml` | E-07, P0.3 |
| Daten-Protokoll (G1→G2) | **HTTP, Pull** — G2 pollt G1 `GET /current` + `GET /health` | — | **E-31 (löst E-30/Push ab)** |
| API-Protokoll (G2→G3) | **HTTP REST** (G3 pollt G2 per `GET`) | — | E-04, E-31 |

> **Hinweis Schwellenwerte:** unberührt vom Stack. Bewertungslogik bleibt eine reine, DB-freie Funktion;
> Schwellen parametrierbar über `config/` (NF-05, E-14) — nie hardcoden (G1-Finalwerte ausstehend).

## 2. Begründung (kompakt — Details in den E-xx)

- **Python + FastAPI + Pydantic + Uvicorn (E-08):** minimaler, schnell produktiver REST-Stack mit
  eingebauter Schema-Validierung — passend für einen 3-Wochen-Prototyp eines Anfänger-Teams. Projektregel
  verlangt eine *begründete* Wahl statt Vorwegnahme; die Sprach-/Framework-Ebene ist damit final.
- **MySQL/MariaDB durchgängig, dev = prod (E-29):** Die DB ist **nicht frei gewählt**, sondern per
  Geschäftsleitung verbindlich vorgegeben (`Surprise Anforderungen.txt`). Da für die moderate Sensordatenrate
  **kein schwerwiegender technischer Gegengrund** besteht (Analyse `Backend-Konzept §6a`), wird die Vorgabe
  angenommen. Variante „eine DB durchgängig" vermeidet den **SQL-Dialekt-Drift** von „SQLite-dev / MySQL-prod".
  Umsetzungskosten gering, weil Persistenz hinter dem Repository-Pattern (SQLAlchemy) DB-agnostisch gekapselt
  ist; der kritische Pfad (Bewertungslogik, ≥ 80 % Coverage) bleibt DB-frei und unberührt.
- **HTTP-Pull statt Push (E-31, löst E-30 ab):** Im realen Seam-Sync stellt **G1** einen abfragbaren
  `GET /current`-Snapshot (+ `GET /health`) bereit; G2 baut einen Poller (Intervall ≤ 60 s, selbst bestimmt).
  Einheitliches Request/Response-Modell über alle Nahtstellen (G3→G2→G1); Fail-safe (NF-01) bleibt erfüllbar,
  indem **Erreichbarkeit** (`/health`/Timeout) getrennt von **Datenaktualität** (`measured_at` zu alt → stale)
  geprüft wird.

## 3. Verworfene Alternativen (Verweis)

| Verworfen | Warum | Bezug |
|---|---|---|
| **SQLite** (durchgängig oder dev-only) | widerspricht GL-Vorgabe; Dialekt-Drift-Risiko | E-29 |
| **PostgreSQL / TimescaleDB** | technisch stark bei Zeitreihen, aber im Haus nicht etabliert (GL-Kriterium „bestehende Kompetenz") | E-29 |
| **Push (`POST /readings`, G2 hostet Ingest)** | durch G1-Realität überholt — G1 hostet einen Abfrage-Endpoint, keinen Sender | E-30→E-31 |
| **Pull mit Einzel-Endpoints je Messgröße** | kein gemeinsamer Mess-Zeitpunkt → inkonsistente Snapshots, verfälscht die 4-Stufen-Logik | E-31 |
| **Stack weiter „offen" halten** | blockiert den Bau; T0-Empfehlung steht, GL setzt die DB | E-08, EP-03 |

## 4. Aufgeräumte Vor-Stände (Drift behoben)

Dieses Blatt ist ab jetzt der **kanonische** P0.1-Stand. Damit sind überholt:
- **E-08** „SQLite + HTTP" → DB-Teil überholt durch **E-29** (MySQL), Protokoll-Teil durch **E-31** (Pull).
  Im ADR-Log bereits als überholt markiert.
- **EP-03** (Session 21.06.) „FastAPI + SQLite + HTTP-POST als Arbeitsannahme" → **doppelt überholt**
  (SQLite→MySQL via E-29; POST→Pull via E-31). War nur eine Task-Zuschnitt-Annahme, keine finale Wahl.
- **Offen / nachzuziehen:** `Projektplan-Jira-Backlog-G2.md` führt teils noch SQLite-Stand
  (im `stand.md` als offener Punkt vermerkt) — gegen dieses Blatt angleichen.

## 5. DoD-Abgleich DTB-2 (P0.1)

- [x] Stack final: Python + FastAPI + Pydantic + **SQLAlchemy + MySQL/MariaDB** + **HTTP-Pull** — siehe §1.
- [x] GL-MySQL-Vorgabe angenommen + Verweis auf Alternativen-/Risiko-Analyse `Backend-Konzept §6a` — §2/§4.
- [x] Begründung + verworfene Alternativen dokumentiert — §2/§3 (+ ADR E-08/E-29/E-31).
- [x] Drift „E-08/EP-03: SQLite+POST" aufgelöst — §4.
- [ ] Restliche Spiegel (`Projektplan-Jira-Backlog-G2.md` SQLite→MySQL) — offen, §4.
