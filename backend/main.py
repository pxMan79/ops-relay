from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from .config import config_loader
from .schemas.models import DatabaseManager
from .routers import servers, collect, history


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    db_config = config_loader.load().database
    db_path = db_config.path
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    
    global db_manager
    db_manager = DatabaseManager(db_path)
    
    print("🚀 服务器监控系统已启动")
    print(f"📊 数据库路径: {db_path}")
    print(f"🌐 API 地址: http://{config_loader.load().api.host}:{config_loader.load().api.port}")
    
    yield
    
    # 关闭时清理资源（如果需要）
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


@app.get("/")
async def root():
    """根路径，返回API信息"""
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


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "timestamp": "2026-05-21T10:30:00Z"}
