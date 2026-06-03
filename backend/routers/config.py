from fastapi import APIRouter, Depends, HTTPException
from config import config_loader
from auth import verify_api_key
from pydantic import BaseModel
from typing import List, Optional


router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
async def get_config():
    config = config_loader.load()
    return {
        "code": 200,
        "data": {
            "servers": config.servers.dict(),
            "alert_thresholds": config.alert_thresholds.dict(),
            "collection": config.collection.dict(),
            "api": {
                "host": config.api.host,
                "port": config.api.port,
                "cors_origins": config.api.cors_origins,
            },
            "database": {
                "retention_days": config.database.retention_days,
            },
            "dingtalk": {
                "enabled": config.dingtalk.enabled,
                "mention_all": config.dingtalk.mention_all,
                "mention_mobiles": config.dingtalk.mention_mobiles,
            },
        },
    }


class AlertThresholdUpdate(BaseModel):
    warning: Optional[float] = None
    critical: Optional[float] = None


class AlertThresholdsUpdate(BaseModel):
    memory: Optional[AlertThresholdUpdate] = None
    disk: Optional[AlertThresholdUpdate] = None
    cpu: Optional[AlertThresholdUpdate] = None


class ConfigUpdateRequest(BaseModel):
    alert_thresholds: Optional[AlertThresholdsUpdate] = None
    collection_cron: Optional[str] = None
    collection_timeout: Optional[int] = None


@router.put("/config", dependencies=[Depends(verify_api_key)])
async def update_config(request: ConfigUpdateRequest):
    import yaml
    from pathlib import Path

    config_path = Path("config.yml")
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="配置文件不存在")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    if request.alert_thresholds:
        if "alert_thresholds" not in raw:
            raw["alert_thresholds"] = {}
        for field in ("memory", "disk", "cpu"):
            update = getattr(request.alert_thresholds, field)
            if update and field not in raw["alert_thresholds"]:
                raw["alert_thresholds"][field] = {}
            if update:
                if update.warning is not None:
                    raw["alert_thresholds"][field]["warning"] = update.warning
                if update.critical is not None:
                    raw["alert_thresholds"][field]["critical"] = update.critical

    if request.collection_cron is not None or request.collection_timeout is not None:
        if "collection" not in raw:
            raw["collection"] = {}
        if request.collection_cron is not None:
            raw["collection"]["cron_expression"] = request.collection_cron
        if request.collection_timeout is not None:
            raw["collection"]["timeout_seconds"] = request.collection_timeout

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True)

    config_loader.reload()

    return {"code": 200, "message": "配置已更新（热加载）"}
