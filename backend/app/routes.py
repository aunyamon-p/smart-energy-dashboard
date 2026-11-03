from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .ingestion import evaluate_observation, normalize_timestamp
from .models import AlertEvent, AnomalyEvidence, EnergyDaily, IngestedEnergy, WeatherAcHourly
from .schemas import (
    AlertDetail,
    AlertDetailResponse,
    AlertListResponse,
    AlertResponse,
    DashboardSummary,
    EnergyListResponse,
    EvidenceResponse,
    IngestEnergyRequest,
    IngestEnergyResponse,
    PageInfo,
    StatusUpdate,
    WeatherContext,
)


router = APIRouter()
TIMEZONE = "Asia/Bangkok"
UTC_PLUS_7 = timezone(timedelta(hours=7))
VALID_LOAD_TYPES = {"AC", "Light", "Plug"}
VALID_STATUSES = {"New", "Acknowledged", "Resolved"}
DATASET_VERSION = "runtime-ingest"


def page_params(page: int, page_size: int) -> tuple[int, int]:
    settings = get_settings()
    if page < 1 or page_size < 1 or page_size > settings.page_size_max:
        raise HTTPException(status_code=422, detail="Invalid pagination parameters")
    return page, page_size


def validate_load_type(load_type: str | None) -> None:
    if load_type and load_type not in VALID_LOAD_TYPES:
        raise HTTPException(status_code=422, detail="Invalid load_type")


def local_bounds(start_date: date | None, end_date: date | None) -> tuple[date | None, date | None]:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    return start_date, end_date


def to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def alert_filters(
    query, start_date: date | None, end_date: date | None, floor: str | None,
    zone: str | None, load_type: str | None, severity: str | None, status: str | None,
):
    validate_load_type(load_type)
    if severity and severity not in {"Low", "Medium", "High"}:
        raise HTTPException(status_code=422, detail="Invalid severity")
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid status")
    start_date, end_date = local_bounds(start_date, end_date)
    if start_date:
        query = query.where(AlertEvent.start_timestamp >= datetime.combine(start_date, time.min, tzinfo=UTC_PLUS_7))
    if end_date:
        query = query.where(AlertEvent.start_timestamp < datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC_PLUS_7))
    for column, value in ((AlertEvent.floor, floor), (AlertEvent.zone, zone), (AlertEvent.load_type, load_type), (AlertEvent.severity, severity), (AlertEvent.status, status)):
        if value:
            query = query.where(column == value)
    return query


def energy_filters(query, start_date, end_date, floor, zone, load_type):
    validate_load_type(load_type)
    start_date, end_date = local_bounds(start_date, end_date)
    for column, value in ((EnergyDaily.floor, floor), (EnergyDaily.zone, zone), (EnergyDaily.load_type, load_type)):
        if value:
            query = query.where(column == value)
    if start_date:
        query = query.where(EnergyDaily.date >= start_date)
    if end_date:
        query = query.where(EnergyDaily.date <= end_date)
    return query


def weather_for_alert(db: Session, alert: AlertEvent) -> WeatherContext | None:
    if alert.load_type != "AC":
        return None
    hour = alert.start_timestamp.replace(minute=0, second=0, microsecond=0)
    row = db.scalar(
        select(WeatherAcHourly).where(
            WeatherAcHourly.floor == alert.floor,
            WeatherAcHourly.zone == alert.zone,
            WeatherAcHourly.timestamp == hour,
        )
    )
    if not row:
        return WeatherContext(status="unavailable", reason="No matching cached AC/weather observation")
    return WeatherContext(
        status="available" if row.join_status == "complete" else "stale",
        timestamp=row.timestamp,
        temperature_2m_c=row.temperature_2m_c,
        relative_humidity_2m_pct=row.relative_humidity_2m_pct,
        ac_context={
            "floor": row.floor,
            "zone": row.zone,
            "ac_power_kw": to_float(row.ac_power_kw),
            "valid_minute_count": row.valid_minute_count,
            "missing_minute_count": row.missing_minute_count,
        },
        reason=None if row.join_status == "complete" else row.join_status,
    )


@router.get("/energy", response_model=EnergyListResponse)
def get_energy(
    start_date: date | None = None, end_date: date | None = None,
    floor: str | None = None, zone: str | None = None, load_type: str | None = None,
    page: int = 1, page_size: int = 50, db: Session = Depends(get_db),
):
    page, page_size = page_params(page, page_size)
    base = energy_filters(select(EnergyDaily), start_date, end_date, floor, zone, load_type)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(EnergyDaily.date, EnergyDaily.floor, EnergyDaily.zone, EnergyDaily.load_type).offset((page - 1) * page_size).limit(page_size)).all()
    return {"data": rows, "pagination": {"page": page, "page_size": page_size, "total": total}, "timezone": TIMEZONE}


@router.get("/alerts", response_model=AlertListResponse)
def get_alerts(
    start_date: date | None = None, end_date: date | None = None,
    floor: str | None = None, zone: str | None = None, load_type: str | None = None,
    severity: str | None = None, status: str | None = None,
    sort: str = "event_time",
    page: int = 1, page_size: int = 50, db: Session = Depends(get_db),
):
    page, page_size = page_params(page, page_size)
    if sort not in {"event_time", "recently_added"}:
        raise HTTPException(status_code=422, detail="Invalid sort")
    base = alert_filters(select(AlertEvent), start_date, end_date, floor, zone, load_type, severity, status)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    order_column = AlertEvent.created_at if sort == "recently_added" else AlertEvent.start_timestamp
    rows = db.scalars(base.order_by(order_column.desc(), AlertEvent.alert_id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"data": rows, "pagination": {"page": page, "page_size": page_size, "total": total}}


@router.post("/ingest", response_model=IngestEnergyResponse, status_code=201)
def ingest_energy(payload: IngestEnergyRequest, db: Session = Depends(get_db)):
    if not payload.source_id.strip():
        raise HTTPException(status_code=422, detail="source_id must not be empty")
    if payload.actual_kw < 0:
        raise HTTPException(status_code=422, detail="actual_kw must be non-negative")
    if payload.interval_minutes < 1 or payload.interval_minutes > 60:
        raise HTTPException(status_code=422, detail="interval_minutes must be between 1 and 60")
    timestamp = normalize_timestamp(payload.timestamp)
    if db.scalar(select(IngestedEnergy).where(IngestedEnergy.source_id == payload.source_id)):
        raise HTTPException(status_code=409, detail="source_id already exists")
    try:
        result = evaluate_observation(
            timestamp, payload.floor, payload.zone, payload.load_type,
            payload.actual_kw, payload.interval_minutes,
        )
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    alert_id = None
    if result["anomaly_detected"]:
        alert_id = f"INGEST-EVENT-{payload.source_id}"
        if db.scalar(select(AlertEvent).where(AlertEvent.alert_id == alert_id)):
            raise HTTPException(status_code=409, detail="Generated alert ID already exists")
        reason = result["reason"]
        excess_energy = result["excess_kw"] * payload.interval_minutes / 60
        db.add(AnomalyEvidence(
            point_alert_id=f"INGEST-{payload.source_id}",
            floor=payload.floor,
            zone=payload.zone,
            load_type=payload.load_type,
            timestamp=timestamp,
            actual_kw=payload.actual_kw,
            expected_kw=result["expected_kw"],
            excess_kw=result["excess_kw"],
            actual_kwh=result["actual_kwh"],
            expected_kwh=result["expected_kwh"],
            excess_kwh=excess_energy,
            severity=result["severity"],
            reason=reason,
            status="New",
            robust_score=result["robust_score"],
            dataset_version=DATASET_VERSION,
        ))
        db.add(AlertEvent(
            alert_id=alert_id,
            floor=payload.floor,
            zone=payload.zone,
            load_type=payload.load_type,
            start_timestamp=timestamp,
            end_timestamp=timestamp,
            duration_minutes=payload.interval_minutes,
            evidence_points=1,
            actual_kw_peak=payload.actual_kw,
            expected_kw_at_peak=result["expected_kw"],
            excess_kw_peak=result["excess_kw"],
            excess_energy_kwh=excess_energy,
            severity=result["severity"],
            reason=reason,
            status="New",
            classification="Potential Anomaly",
            dataset_version=DATASET_VERSION,
        ))
    db.add(IngestedEnergy(
        source_id=payload.source_id,
        timestamp=timestamp,
        floor=payload.floor,
        zone=payload.zone,
        load_type=payload.load_type,
        actual_kw=payload.actual_kw,
        interval_minutes=payload.interval_minutes,
        anomaly_detected=result["anomaly_detected"],
        alert_id=alert_id,
        dataset_version=DATASET_VERSION,
    ))
    db.commit()
    return {**payload.model_dump(), **result, "timestamp": timestamp, "alert_id": alert_id}


@router.get("/alerts/{alert_id}", response_model=AlertDetailResponse)
def get_alert(alert_id: str, db: Session = Depends(get_db)):
    alert = db.scalar(select(AlertEvent).where(AlertEvent.alert_id == alert_id))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    evidence = db.scalars(
        select(AnomalyEvidence).where(
            AnomalyEvidence.floor == alert.floor,
            AnomalyEvidence.zone == alert.zone,
            AnomalyEvidence.load_type == alert.load_type,
            AnomalyEvidence.timestamp >= alert.start_timestamp,
            AnomalyEvidence.timestamp <= alert.end_timestamp,
        ).order_by(AnomalyEvidence.timestamp)
    ).all()
    detail = AlertDetail.model_validate({
        **{field: getattr(alert, field) for field in (
            "alert_id", "created_at", "floor", "zone", "load_type", "start_timestamp", "end_timestamp",
            "duration_minutes", "evidence_points", "actual_kw_peak", "expected_kw_at_peak",
            "excess_kw_peak", "excess_energy_kwh", "severity", "reason", "status", "classification",
        )},
        "evidence": evidence,
        "weather_context": weather_for_alert(db, alert),
    })
    return {"data": detail}


@router.patch("/alerts/{alert_id}", response_model=AlertResponse)
def update_alert(alert_id: str, payload: StatusUpdate, db: Session = Depends(get_db)):
    alert = db.scalar(select(AlertEvent).where(AlertEvent.alert_id == alert_id))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = payload.status
    alert.status_updated_at = datetime.now(UTC_PLUS_7)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    start_date: date | None = None, end_date: date | None = None,
    floor: str | None = None, zone: str | None = None, load_type: str | None = None,
    include_weather: bool = True, db: Session = Depends(get_db),
):
    base = energy_filters(select(EnergyDaily), start_date, end_date, floor, zone, load_type)
    rows = db.scalars(base).all()
    event_query = alert_filters(select(AlertEvent), start_date, end_date, floor, zone, load_type, None, None)
    events = db.scalars(event_query).all()
    severity_counts = {severity: sum(event.severity == severity for event in events) for severity in ("High", "Medium", "Low")}
    period_start = start_date.isoformat() if start_date else min((row.date for row in rows), default=None)
    period_end = end_date.isoformat() if end_date else max((row.date for row in rows), default=None)
    weather_context = None
    if include_weather:
        weather_context = {
            "source": "Open-Meteo",
            "timezone": TIMEZONE,
            "status": "cached",
            "note": "Weather is contextual information and does not change anomaly severity.",
        }
    return {
        "period": {"start": period_start, "end": period_end},
        "timezone": TIMEZONE,
        "actual_energy_kwh": sum((row.actual_energy_kwh or Decimal("0")) for row in rows),
        "expected_energy_kwh": sum((row.expected_energy_kwh or Decimal("0")) for row in rows),
        "excess_energy_kwh": sum((row.excess_energy_kwh or Decimal("0")) for row in rows),
        "potential_anomaly_event_count": len(events),
        "severity_counts": severity_counts,
        "missing_observations": sum(row.missing_observations for row in rows),
        "partial_component_observations": sum(row.partial_component_observations for row in rows),
        "weather_context": weather_context,
    }


@router.get("/analytics/weather-ac")
def weather_ac_analytics(
    start_date: date | None = None,
    end_date: date | None = None,
    floor: str | None = None,
    zone: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    page, page_size = page_params(page, page_size)
    start_date, end_date = local_bounds(start_date, end_date)
    query = select(WeatherAcHourly)
    if floor:
        query = query.where(WeatherAcHourly.floor == floor)
    if zone:
        query = query.where(WeatherAcHourly.zone == zone)
    if start_date:
        query = query.where(WeatherAcHourly.timestamp >= datetime.combine(start_date, time.min, tzinfo=UTC_PLUS_7))
    if end_date:
        query = query.where(WeatherAcHourly.timestamp < datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC_PLUS_7))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(WeatherAcHourly.timestamp, WeatherAcHourly.floor, WeatherAcHourly.zone)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    complete = sum(row.join_status == "complete" for row in rows)
    return {
        "data": [
            {
                "floor": row.floor,
                "zone": row.zone,
                "timestamp": row.timestamp.replace(tzinfo=UTC_PLUS_7),
                "ac_power_kw": row.ac_power_kw,
                "valid_minute_count": row.valid_minute_count,
                "expected_minute_count": row.expected_minute_count,
                "missing_minute_count": row.missing_minute_count,
                "temperature_2m_c": row.temperature_2m_c,
                "relative_humidity_2m_pct": row.relative_humidity_2m_pct,
                "join_status": row.join_status,
            }
            for row in rows
        ],
        "pagination": {"page": page, "page_size": page_size, "total": total},
        "timezone": TIMEZONE,
        "source": "Open-Meteo",
        "complete_rows_on_page": complete,
        "note": "Weather is contextual information and does not change anomaly severity.",
    }
