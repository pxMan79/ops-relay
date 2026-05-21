from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional

from ..models import (
    ServerStatusResponse,
    ServerListResponse,
    HistoryQueryParams,
    HistoryResponse,
)
from ..config import config_loader
from ..schemas.models import DatabaseManager, HistorySnapshot


router = APIRouter(prefix="/api", tags=["servers"])


@router.get("/servers", response_model=ServerListResponse)
async def get_all_servers():
    """获取所有服务器的最新监控状态"""
    db_config = config_loader.load().database
    db = DatabaseManager(db_config.path)
    collector_service = __import__("backend.services.collector", fromlist=["CollectorService"]).CollectorService(db)

    try:
        servers_data = collector_service.get_latest_status()

        # 计算统计信息
        total = len(servers_data)
        online = total  # 假设能查到的都是在线的
        alert_count = sum(
            1 for s in servers_data
            if s.get("memory_percent", 0) >= 80 or any(
                d.get("usage_percent", 0) >= 80
                for d in s.get("disks_info", {}).get("data_disks", [])
            )
        )

        return ServerListResponse(
            code=200,
            data=[
                ServerStatusResponse(**s, overall_status=_calculate_overall_status(s))
                for s in servers_data
            ],
            meta={
                "total": total,
                "online": online,
                "alert_count": alert_count,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers/{ip}", response_model=ServerStatusResponse)
async def get_server_by_ip(ip: str):
    """获取指定 IP 服务器的详细信息"""
    db_config = config_loader.load().database
    db = DatabaseManager(db_config.path)

    try:
        # 这里简化实现，实际应该查询数据库
        raise HTTPException(status_code=501, detail="功能开发中")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _calculate_overall_status(server_data: dict) -> str:
    """计算服务器整体状态"""
    thresholds = config_loader.get_alert_thresholds()

    memory_pct = server_data.get("memory_percent", 0)
    if memory_pct >= thresholds.memory.critical:
        return "critical"
    if memory_pct >= thresholds.memory.warning:
        return "warning"

    disks_info = server_data.get("disks_info", {})
    if isinstance(disks_info, dict):
        system_disk = disks_info.get("system_disk", "")
        if "%" in system_disk:
            try:
                pct = float(system_disk.split("%")[0].split()[-1])
                if pct >= thresholds.disk.critical:
                    return "critical"
                if pct >= thresholds.disk.warning:
                    return "warning"
            except Exception:
                pass

    return "normal"
