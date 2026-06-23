"""G1-Poller: holt GET /current, validiert das Snapshot-JSON und speichert ein Reading.

Der Poller bleibt DB-agnostisch (ruft Repository.save; MySQL-Implementierung via DTB-28).
Er nutzt das Reading-Schema aus DTB-12 (src/model/schemas.py) und fuehrt keine
eigenstaendige Schema-Definition.

Bezug: Pull-Protokoll E-31; Datenmodell DTB-12; Persistenz DTB-28.
"""

import logging
from datetime import UTC, datetime

import httpx

from src.model.enums import SensorStatus, Source
from src.model.schemas import Reading
from src.storage.repository import Repository

logger = logging.getLogger(__name__)

# Physikalische Plausibilitaetsgrenzen fuer die Eingangsvalidierung.
# (Bewertungsschwellen kommen aus config/ und werden hier NICHT hardgecoded.)
MIN_TEMP_C = -50.0
MAX_TEMP_C = 50.0
MIN_HUMIDITY_PCT = 0.0
MAX_HUMIDITY_PCT = 100.0
MIN_PRESSURE_HPA = 800.0
MAX_PRESSURE_HPA = 1100.0

REQUIRED_FIELDS = ("measured_at", "sensor_id", "surface_temp_c", "air_temp_c", "humidity_pct")


class Poller:
    """HTTP-Client gegen G1 GET /current mit Eingangsvalidierung."""

    def __init__(self, base_url: str, repository: Repository, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.repository = repository
        self.timeout = timeout

    def poll(self) -> Reading | None:
        """Holt Snapshot von G1, validiert ihn und speichert ein Reading.

        Bei jeder Art von Fehler (HTTP, Parsing, fehlende Pflichtfelder,
        Out-of-Range) wird geloggt und None zurueckgegeben -> kein Speichern,
        kein GRUEN (Fail-safe).
        """
        url = f"{self.base_url}/current"
        try:
            response = httpx.get(url, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("G1-Poll fehlgeschlagen: %s", exc)
            return None

        try:
            data = response.json()
        except Exception as exc:  # pragma: no cover - JSON-Fehler sind schwer robust zu testen
            logger.error("G1-Antwort nicht als JSON parsierbar: %s", exc)
            return None

        reading = self._build_reading(data)
        if reading is None:
            return None

        try:
            reading_id = self.repository.save(reading)
        except Exception as exc:  # pragma: no cover - Repository-Fehler aus DTB-28
            logger.error("Speichern des Readings fehlgeschlagen: %s", exc)
            return None

        logger.info(
            "Reading gespeichert: id=%s sensor=%s measured_at=%s",
            reading_id,
            reading.sensor_id,
            reading.measured_at.isoformat(),
        )
        return reading

    def _build_reading(self, data: object) -> Reading | None:
        if not isinstance(data, dict):
            logger.error("G1-Antwort ist kein JSON-Objekt: %s", type(data))
            return None

        for field in REQUIRED_FIELDS:
            if field not in data:
                logger.error("Pflichtfeld in G1-Antwort fehlt: %s", field)
                return None

        try:
            measured_at = _parse_iso_utc(data["measured_at"])
            sensor_id = _as_string(data["sensor_id"], "sensor_id")
            surface_temp_c = _as_float(data["surface_temp_c"], "surface_temp_c")
            air_temp_c = _as_float(data["air_temp_c"], "air_temp_c")
            humidity_pct = _as_float(data["humidity_pct"], "humidity_pct")
        except ValueError as exc:
            logger.error("G1-Feld ungueltig: %s", exc)
            return None

        if not (MIN_TEMP_C <= surface_temp_c <= MAX_TEMP_C):
            logger.error(
                "surface_temp_c ausserhalb des gueltigen Bereichs: %s", surface_temp_c
            )
            return None
        if not (MIN_TEMP_C <= air_temp_c <= MAX_TEMP_C):
            logger.error("air_temp_c ausserhalb des gueltigen Bereichs: %s", air_temp_c)
            return None
        if not (MIN_HUMIDITY_PCT <= humidity_pct <= MAX_HUMIDITY_PCT):
            logger.error("humidity_pct ausserhalb des gueltigen Bereichs: %s", humidity_pct)
            return None

        pressure_hpa = _optional_float(data.get("pressure_hpa"), "pressure_hpa")
        if pressure_hpa is not None and not (MIN_PRESSURE_HPA <= pressure_hpa <= MAX_PRESSURE_HPA):
            logger.error("pressure_hpa ausserhalb des gueltigen Bereichs: %s", pressure_hpa)
            return None

        status = _optional_status(data.get("status"))
        if status is None:
            return None

        return Reading(
            sensor_id=sensor_id,
            measured_at=measured_at,
            surface_temp_c=surface_temp_c,
            air_temp_c=air_temp_c,
            humidity_pct=humidity_pct,
            pressure_hpa=pressure_hpa,
            status=status,
            received_at=datetime.now(UTC),
            source=Source.REAL,
        )


def _parse_iso_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"measured_at muss ein String sein, erhalten: {type(value)}")
    # Python <3.11 akzeptiert 'Z' nicht direkt; ab 3.11 geht es.
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("measured_at muss Zeitzoneninformation enthalten (UTC)")
    return parsed.astimezone(UTC)


def _as_string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} muss ein String sein, erhalten: {type(value)}")
    if not value.strip():
        raise ValueError(f"{field} darf nicht leer sein")
    return value


def _as_float(value: object, field: str) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} muss eine Zahl sein, erhalten: {value!r}") from exc


def _optional_float(value: object, field: str) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} muss eine Zahl sein, erhalten: {value!r}") from exc


def _optional_status(value: object) -> SensorStatus | None:
    if value is None:
        return SensorStatus.OK
    if not isinstance(value, str):
        logger.error("status muss ein String sein, erhalten: %s", type(value))
        return None
    try:
        return SensorStatus(value)
    except ValueError:
        logger.error("Ungueltiger status-Wert: %s", value)
        return None
