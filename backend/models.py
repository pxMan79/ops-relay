from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class DiskInfo(BaseModel):
    mount_point: str
    size_gb: float = 0.0
    used_gb: float = 0.0
    usage_percent: float = 0.0
    status: str = "normal"


class MemoryInfo(BaseModel):
    total_gb: float = 0.0
    used_gb: float = 0.0
    usage_percent: float = 0.0
    status: str = "normal"


class ServerStatusResponse(BaseModel):
    id: int
    ip: str
    hostname: str = ""
    os_version: str = ""
    uptime: str = ""
    cpu_usage: float = 0.0
    memory: MemoryInfo = Field(default_factory=MemoryInfo)
    disks: List[DiskInfo] = Field(default_factory=list)
    last_update: Optional[datetime] = None
    overall_status: str = "normal"


class ServerListResponse(BaseModel):
    code: int = 200
    data: List[ServerStatusResponse] = []
    meta: dict = {}


class CollectRequest(BaseModel):
    group: Optional[str] = None
    force: bool = False


class CollectResponse(BaseModel):
    code: int = 200
    message: str = ""
    task_id: str = ""
    estimated_time: str = ""


class HistoryQueryParams(BaseModel):
    ip: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    interval: str = "1h"


class HistoryResponse(BaseModel):
    code: int = 200
    data: dict = {}
