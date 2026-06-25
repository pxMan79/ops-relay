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


class StorageDeviceInfo(BaseModel):
    name: str = ""
    model: str = ""
    size_gb: float = 0.0


class GpuInfo(BaseModel):
    name: str = ""
    vendor: str = ""
    memory_mb: float = 0.0
    memory_text: str = ""
    driver: str = ""


class HardwareInfo(BaseModel):
    memory_size_gb: float = 0.0
    storage_devices: List[StorageDeviceInfo] = Field(default_factory=list)
    gpu_devices: List[GpuInfo] = Field(default_factory=list)


class ServerStatusResponse(BaseModel):
    id: int
    ip: str
    hostname: str = ""
    os_type: str = ""
    group_name: str = ""
    os_version: str = ""
    uptime: str = ""
    cpu_usage: float = 0.0
    cpu_text: str = ""
    memory: MemoryInfo = Field(default_factory=MemoryInfo)
    memory_text: str = ""
    disks: List[DiskInfo] = Field(default_factory=list)
    system_disk_text: str = ""
    data_disk_text: str = ""
    hardware: HardwareInfo = Field(default_factory=HardwareInfo)
    last_update: Optional[datetime] = None
    overall_status: str = "normal"
    collection_status: str = "success"
    collection_error: str = ""


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
    total_count: int = 0
    success_count: int = 0
    failed_count: int = 0


class HistoryQueryParams(BaseModel):
    ip: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    interval: str = "1h"


class HistoryResponse(BaseModel):
    code: int = 200
    data: dict = {}
