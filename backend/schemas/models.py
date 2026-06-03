from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os

Base = declarative_base()


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip = Column(String(50), unique=True, nullable=False, index=True)
    hostname = Column(String(100), default="")
    os_type = Column(String(20), default="linux")
    os_version = Column(String(100), default="")
    group_name = Column(String(50), default="default")
    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    history_snapshots = relationship("HistorySnapshot", back_populates="server", cascade="all, delete-orphan")
    alerts = relationship("AlertLog", back_populates="server", cascade="all, delete-orphan")


class HistorySnapshot(Base):
    __tablename__ = "history_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True)
    cpu_usage = Column(Float, default=0.0)
    memory_total_mb = Column(Float, default=0.0)
    memory_used_mb = Column(Float, default=0.0)
    memory_percent = Column(Float, default=0.0)
    disks_info = Column(JSON, default=dict)
    uptime_seconds = Column(Integer, default=0)
    collected_at = Column(DateTime, default=datetime.utcnow, index=True)

    server = relationship("Server", back_populates="history_snapshots")


class AlertLog(Base):
    __tablename__ = "alerts_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type = Column(String(20), nullable=False)  # memory/disk/cpu
    severity = Column(String(20), nullable=False)  # warning/critical
    threshold_value = Column(Float, default=0.0)
    actual_value = Column(Float, default=0.0)
    message = Column(Text, default="")
    is_resolved = Column(Boolean, default=False, index=True)
    triggered_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)

    server = relationship("Server", back_populates="alerts")


_engines = {}


def get_engine(db_path: str):
    abs_path = os.path.abspath(db_path)
    if abs_path not in _engines:
        os.makedirs(os.path.dirname(abs_path) if os.path.dirname(abs_path) else ".", exist_ok=True)
        engine = create_engine(f"sqlite:///{abs_path}", echo=False)
        Base.metadata.create_all(engine)
        _engines[abs_path] = engine
    return _engines[abs_path]


class DatabaseManager:
    def __init__(self, db_path: str = "./monitoring.db"):
        self._engine = get_engine(db_path)
        self._SessionLocal = sessionmaker(bind=self._engine)

    @property
    def engine(self):
        return self._engine

    def get_session(self):
        return self._SessionLocal()

    def get_db(self):
        db = self._SessionLocal()
        try:
            yield db
        finally:
            db.close()
