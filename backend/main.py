from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit

from config import config_loader
from schemas.models import DatabaseManager
from services.collector import CollectorService
from routers import servers, collect, history, config

scheduler = BackgroundScheduler()


def scheduled_collect():
    try:
        db_config = config_loader.load().database
        db = DatabaseManager(db_config.path)
        collector = CollectorService(db)
        data = collector.collect_all()
        if data:
            collector.save_to_database(data)
            print(f"⏰ 定时采集完成: {len(data)} 台服务器")
    except Exception as e:
        print(f"❌ 定时采集失败: {e}")


def cleanup_old_data():
    try:
        db_config = config_loader.load().database
        db = DatabaseManager(db_config.path)
        session = db.get_session()

        from datetime import timedelta
        from schemas.models import HistorySnapshot, AlertLog

        retention_days = db_config.retention_days
        cutoff = datetime.utcnow() - timedelta(days=retention_days)

        deleted_snapshots = session.query(HistorySnapshot).filter(
            HistorySnapshot.collected_at < cutoff
        ).delete()

        deleted_alerts = session.query(AlertLog).filter(
            AlertLog.is_resolved == True,
            AlertLog.resolved_at < cutoff
        ).delete()

        session.commit()

        if deleted_snapshots or deleted_alerts:
            print(f"🧹 数据清理完成: 删除 {deleted_snapshots} 条历史快照, {deleted_alerts} 条已恢复告警")

        session.close()
    except Exception as e:
        print(f"❌ 数据清理失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    db_config = config_loader.load().database
    db_path = db_config.path
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

    global db_manager
    db_manager = DatabaseManager(db_path)

    cron_expr = config_loader.load().collection.cron_expression
    if cron_expr:
        try:
            parts = cron_expr.split()
            trigger = CronTrigger(
                minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4]
            )
            scheduler.add_job(scheduled_collect, trigger, id="scheduled_collect", replace_existing=True)
            scheduler.add_job(
                cleanup_old_data,
                CronTrigger(hour=3, minute=0),
                id="cleanup_old_data",
                replace_existing=True,
            )
            scheduler.start()
            print(f"⏰ 定时采集已启动: {cron_expr}")
            print("🧹 每日数据清理已启动: 03:00")
        except Exception as e:
            print(f"⚠️ 定时任务配置错误: {e}")

    print("🚀 服务器监控系统已启动")
    print(f"📊 数据库路径: {db_path}")
    print(f"🌐 API 地址: http://{config_loader.load().api.host}:{config_loader.load().api.port}")

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)
    print("👋 服务器监控系统已关闭")


# 创建 FastAPI 应用实例
app = FastAPI(
    title="服务器监控系统",
    description="基于 Ansible 的内网服务器监控平台 API",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置 CORS
api_config = config_loader.load().api
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(servers.router)
app.include_router(collect.router)
app.include_router(history.router)


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================
# 前端 SPA 静态托管（单体容器模式）
# 容器内 /app/static 放 Vue 构建产物（dist）。
# /api、/health、/docs 等路由在上方先注册，优先匹配；
# 其余路径走静态文件，找不到时回退 index.html（支持 Vue Router history 模式）。
# 开发态（无 STATIC_DIR）则提供 / 信息接口，前端走 vite dev server。
# ============================================
STATIC_DIR = os.environ.get("STATIC_DIR", "/app/static")


class SPAStaticFiles(StaticFiles):
    """静态文件 + 单页应用回退：未命中的路径返回 index.html。"""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise exc


if os.path.isdir(STATIC_DIR):
    app.mount("/", SPAStaticFiles(directory=STATIC_DIR, html=True), name="spa")
    print(f"🎨 前端静态资源已挂载: {STATIC_DIR}")
else:
    @app.get("/")
    async def root():
        """根路径，返回 API 信息（仅开发态，生产由 SPA 接管 /）"""
        return {
            "name": "服务器监控系统 API",
            "version": "1.0.0",
            "docs": "/docs",
            "endpoints": {
                "servers": "/api/servers",
                "collect": "/api/collect",
                "history": "/api/history",
            },
        }
