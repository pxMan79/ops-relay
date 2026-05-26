from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional

from models import HistoryQueryParams, HistoryResponse
from config import config_loader
from schemas.models import DatabaseManager, HistorySnapshot, Server


router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    ip: Optional[str] = Query(None, description="过滤指定服务器IP"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    interval: str = Query("1h", description="聚合间隔: 5m/1h/1d"),
):
    """获取历史记录"""
    db_config = config_loader.load().database
    db = DatabaseManager(db_config.path)
    session = db.get_session()

    try:
        # 默认查询最近24小时
        if not end_time:
            end_time = datetime.utcnow()
        if not start_time:
            start_time = end_time - timedelta(hours=24)

        # 构建查询
        query = session.query(HistorySnapshot).filter(
            HistorySnapshot.collected_at >= start_time,
            HistorySnapshot.collected_at <= end_time,
        )

        if ip:
            server = session.query(Server).filter_by(ip=ip).first()
            if not server:
                raise HTTPException(status_code=404, detail=f"服务器 {ip} 不存在")
            query = query.filter(HistorySnapshot.server_id == server.id)

        # 按时间排序
        snapshots = query.order_by(HistorySnapshot.collected_at.asc()).all()

        # 聚合数据
        timestamps = []
        series_dict = {}

        for snap in snapshots:
            server = session.query(Server).get(snap.server_id)
            server_ip = server.ip if server else "unknown"

            time_key = snap.collected_at.strftime("%Y-%m-%d %H:%M")

            if time_key not in timestamps:
                timestamps.append(time_key)

            if server_ip not in series_dict:
                series_dict[server_ip] = {
                    "ip": server_ip,
                    "cpu_usage": [],
                    "memory_percent": [],
                    "disk_percent": [],
                }

            series_dict[server_ip]["cpu_usage"].append(round(snap.cpu_usage, 1))
            series_dict[server_ip]["memory_percent"].append(round(snap.memory_percent, 1))

            # 计算最大磁盘使用率
            max_disk_pct = 0
            if snap.disks_info and isinstance(snap.disks_info, dict):
                system_disk = snap.disks_info.get("system_disk", "")
                if "%" in system_disk:
                    try:
                        max_disk_pct = float(system_disk.split("%")[0].split()[-1])
                    except Exception:
                        pass
            series_dict[server_ip]["disk_percent"].append(max_disk_pct)

        return HistoryResponse(
            code=200,
            data={
                "timestamps": timestamps,
                "series": list(series_dict.values()),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
