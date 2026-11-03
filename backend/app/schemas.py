from datetime import date, datetime, timezone, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer


class PageInfo(BaseModel):
    page: int
    page_size: int
    total: int


class EnergyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: date
    floor: str
    zone: str
    load_type: Literal["AC", "Light", "Plug"]
    actual_energy_kwh: float | None
    expected_energy_kwh: float | None
    excess_energy_kwh: float | None
    observations: int
    missing_observations: int
    partial_component_observations: int


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    alert_id: str
    created_at: datetime
    floor: str
    zone: str
    load_type: Literal["AC", "Light", "Plug"]
    start_timestamp: datetime
    end_timestamp: datetime
    duration_minutes: int
    evidence_points: int
    actual_kw_peak: float
    expected_kw_at_peak: float
    excess_kw_peak: float
    excess_energy_kwh: float
    severity: Literal["Low", "Medium", "High"]
    reason: str
    status: Literal["New", "Acknowledged", "Resolved"]
    classification: Literal["Potential Anomaly"]

    @field_serializer("created_at", "start_timestamp", "end_timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone(timedelta(hours=7)))
        return value.isoformat()


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    point_alert_id: str
    timestamp: datetime
    actual_kw: float
    expected_kw: float
    excess_kw: float
    actual_kwh: float
    expected_kwh: float
    excess_kwh: float
    severity: Literal["Low", "Medium", "High"]
    reason: str
    status: Literal["New", "Acknowledged", "Resolved"]
    robust_score: float

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone(timedelta(hours=7)))
        return value.isoformat()


class WeatherContext(BaseModel):
    status: Literal["available", "stale", "unavailable"]
    source: str = "Open-Meteo"
    timezone: str = "Asia/Bangkok"
    timestamp: datetime | None = None
    temperature_2m_c: float | None = None
    relative_humidity_2m_pct: float | None = None
    ac_context: dict | None = None
    reason: str | None = None

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone(timedelta(hours=7)))
        return value.isoformat()


class AlertDetail(AlertResponse):
    evidence: list[EvidenceResponse]
    weather_context: WeatherContext | None


class DashboardSummary(BaseModel):
    period: dict
    timezone: str
    actual_energy_kwh: float
    expected_energy_kwh: float
    excess_energy_kwh: float
    potential_anomaly_event_count: int
    severity_counts: dict[str, int]
    missing_observations: int
    partial_component_observations: int
    estimated_cost: None = None
    cost_status: Literal["not_configured"] = "not_configured"
    weather_context: dict | None


class StatusUpdate(BaseModel):
    status: Literal["New", "Acknowledged", "Resolved"]


class IngestEnergyRequest(BaseModel):
    source_id: str
    timestamp: datetime
    floor: str
    zone: str
    load_type: Literal["AC", "Light", "Plug"]
    actual_kw: float
    interval_minutes: int = 1


class IngestEnergyResponse(BaseModel):
    source_id: str
    timestamp: datetime
    floor: str
    zone: str
    load_type: Literal["AC", "Light", "Plug"]
    actual_kw: float
    expected_kw: float | None
    excess_kw: float
    actual_kwh: float
    expected_kwh: float | None
    robust_score: float | None
    anomaly_detected: bool
    alert_id: str | None
    severity: Literal["Low", "Medium", "High"] | None
    reason: str | None

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone(timedelta(hours=7)))
        return value.isoformat()


class EnergyListResponse(BaseModel):
    data: list[EnergyResponse]
    pagination: PageInfo
    timezone: str


class AlertListResponse(BaseModel):
    data: list[AlertResponse]
    pagination: PageInfo


class AlertDetailResponse(BaseModel):
    data: AlertDetail
