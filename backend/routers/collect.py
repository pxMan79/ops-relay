from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from datetime import datetime
import uuid

from models import CollectRequest, CollectResponse
from config import config_loader
from schemas.models import DatabaseManager
from services.collector import CollectorService
from auth import verify_api_key


router = APIRouter(prefix="/api", tags=["collection"])


@router.post("/collect", response_model=CollectResponse, dependencies=[Depends(verify_api_key)])
async def trigger_collection(
    request: CollectRequest = None,
    background_tasks: BackgroundTasks = None,
):
    """手动触发一次全网数据采集"""
    task_id = str(uuid.uuid4())[:8]

    try:
        db_config = config_loader.load().database
        db = DatabaseManager(db_config.path)
        collector = CollectorService(db)

        # 执行数据采集
        data = collector.collect_all()

        if not data:
            return CollectResponse(
                code=200,
                message="未采集到数据，请检查 Ansible 配置",
                task_id=task_id,
                estimated_time="0秒",
            )

        # 保存到数据库
        collector.save_to_database(data)
        success_count = sum(1 for item in data if item.get("采集状态") == "success")
        failed_count = len(data) - success_count

        return CollectResponse(
            code=200,
            message=f"成功采集 {success_count}/{len(data)} 台服务器数据",
            task_id=task_id,
            estimated_time=f"{len(data) * 2}秒",
            total_count=len(data),
            success_count=success_count,
            failed_count=failed_count,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"采集失败: {str(e)}")
