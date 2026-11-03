from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class EnergyDaily(Base):
    __tablename__ = "energy_daily"
    __table_args__ = (
        UniqueConstraint("floor", "zone", "load_type", "date", name="uq_energy_dimension_date"),
        Index("ix_energy_date", "date"),
        Index("ix_energy_dimension", "floor", "zone", "load_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    floor: Mapped[str] = mapped_column(String(32), nullable=False)
    zone: Mapped[str] = mapped_column(String(32), nullable=False)
    load_type: Mapped[str] = mapped_column(String(16), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_energy_kwh: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    expected_energy_kwh: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    excess_energy_kwh: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    observations: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_observations: Mapped[int] = mapped_column(Integer, nullable=False)
    partial_component_observations: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(128), nullable=False)


class IngestedEnergy(Base):
    __tablename__ = "ingested_energy"
    __table_args__ = (
        UniqueConstraint("source_id", name="uq_ingested_energy_source_id"),
        Index("ix_ingested_energy_timestamp", "timestamp"),
        Index("ix_ingested_energy_dimension", "floor", "zone", "load_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    floor: Mapped[str] = mapped_column(String(32), nullable=False)
    zone: Mapped[str] = mapped_column(String(32), nullable=False)
    load_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actual_kw: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    anomaly_detected: Mapped[bool] = mapped_column(nullable=False, default=False)
    alert_id: Mapped[str | None] = mapped_column(String(64))
    dataset_version: Mapped[str] = mapped_column(String(128), nullable=False)


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (
        UniqueConstraint("alert_id", name="uq_alert_id"),
        Index("ix_alert_start", "start_timestamp"),
        Index("ix_alert_filters", "floor", "zone", "load_type", "severity", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.current_timestamp(),
    )
    floor: Mapped[str] = mapped_column(String(32), nullable=False)
    zone: Mapped[str] = mapped_column(String(32), nullable=False)
    load_type: Mapped[str] = mapped_column(String(16), nullable=False)
    start_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_points: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_kw_peak: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    expected_kw_at_peak: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    excess_kw_peak: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    excess_energy_kwh: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="New")
    classification: Mapped[str] = mapped_column(String(32), nullable=False, default="Potential Anomaly")
    dataset_version: Mapped[str] = mapped_column(String(128), nullable=False)
    status_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnomalyEvidence(Base):
    __tablename__ = "anomaly_evidence"
    __table_args__ = (
        UniqueConstraint("point_alert_id", name="uq_point_alert_id"),
        Index("ix_evidence_event_lookup", "floor", "zone", "load_type", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    point_alert_id: Mapped[str] = mapped_column(String(64), nullable=False)
    floor: Mapped[str] = mapped_column(String(32), nullable=False)
    zone: Mapped[str] = mapped_column(String(32), nullable=False)
    load_type: Mapped[str] = mapped_column(String(16), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_kw: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    expected_kw: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    excess_kw: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    actual_kwh: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    expected_kwh: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    excess_kwh: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    robust_score: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(128), nullable=False)


class WeatherHourly(Base):
    __tablename__ = "weather_hourly"
    __table_args__ = (
        UniqueConstraint("timestamp", name="uq_weather_timestamp"),
        Index("ix_weather_timestamp", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    temperature_2m_c: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    relative_humidity_2m_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(128))


class WeatherAcHourly(Base):
    __tablename__ = "weather_ac_hourly"
    __table_args__ = (
        UniqueConstraint("floor", "zone", "timestamp", name="uq_weather_ac_dimension_timestamp"),
        Index("ix_weather_ac_lookup", "floor", "zone", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    floor: Mapped[str] = mapped_column(String(32), nullable=False)
    zone: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ac_power_kw: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    valid_minute_count: Mapped[int | None] = mapped_column(Integer)
    expected_minute_count: Mapped[int | None] = mapped_column(Integer)
    missing_minute_count: Mapped[int | None] = mapped_column(Integer)
    temperature_2m_c: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    relative_humidity_2m_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    join_status: Mapped[str] = mapped_column(String(24), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(128), nullable=False)
