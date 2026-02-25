import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ServerSource(str, enum.Enum):
    cloud = "cloud"
    dedicated = "dedicated"


class UtilizationTier(str, enum.Enum):
    idle = "idle"
    low = "low"
    moderate = "moderate"
    high = "high"
    critical = "critical"


class ServiceType(str, enum.Enum):
    docker = "docker"
    systemd = "systemd"
    port = "port"


class Confidence(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class RecommendationStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    dismissed = "dismissed"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hetzner_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    server_type: Mapped[str] = mapped_column(String(64))
    source: Mapped[ServerSource] = mapped_column(Enum(ServerSource))
    status: Mapped[str] = mapped_column(String(32), default="running")
    datacenter: Mapped[str] = mapped_column(String(64), default="")
    ipv4: Mapped[str] = mapped_column(String(45), default="")
    cores: Mapped[int] = mapped_column(Integer, default=0)
    memory_gb: Mapped[float] = mapped_column(Float, default=0.0)
    disk_gb: Mapped[int] = mapped_column(Integer, default=0)
    monthly_cost_eur: Mapped[float] = mapped_column(Float, default=0.0)
    labels: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    metrics: Mapped[list["MetricSnapshot"]] = relationship(back_populates="server", cascade="all, delete-orphan")
    services: Mapped[list["RunningService"]] = relationship(back_populates="server", cascade="all, delete-orphan")


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    cpu_percent: Mapped[float] = mapped_column(Float, default=0.0)
    memory_percent: Mapped[float] = mapped_column(Float, default=0.0)
    disk_percent: Mapped[float] = mapped_column(Float, default=0.0)
    network_in_mbps: Mapped[float] = mapped_column(Float, default=0.0)
    network_out_mbps: Mapped[float] = mapped_column(Float, default=0.0)
    load_avg_1m: Mapped[float | None] = mapped_column(Float, nullable=True)

    server: Mapped["Server"] = relationship(back_populates="metrics")


class RunningService(Base):
    __tablename__ = "running_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    service_type: Mapped[ServiceType] = mapped_column(Enum(ServiceType))
    name: Mapped[str] = mapped_column(String(255))
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    memory_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    server: Mapped["Server"] = relationship(back_populates="services")


class ConsolidationRecommendation(Base):
    __tablename__ = "consolidation_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_name: Mapped[str] = mapped_column(String(255))
    server_ids: Mapped[list] = mapped_column(JSON)
    target_server_type: Mapped[str] = mapped_column(String(64))
    current_total_cost_eur: Mapped[float] = mapped_column(Float)
    projected_cost_eur: Mapped[float] = mapped_column(Float)
    monthly_savings_eur: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Confidence] = mapped_column(Enum(Confidence), default=Confidence.medium)
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus), default=RecommendationStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
