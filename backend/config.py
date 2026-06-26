import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    ip: str
    priority: int = 0


class AlertThreshold(BaseModel):
    warning: float = 80.0
    critical: float = 90.0


class AlertThresholdsConfig(BaseModel):
    memory: AlertThreshold = AlertThreshold()
    disk: AlertThreshold = Field(default_factory=lambda: AlertThreshold(warning=85, critical=95))
    cpu: AlertThreshold = Field(default_factory=lambda: AlertThreshold(warning=85, critical=95))
    swap: AlertThreshold = Field(default_factory=lambda: AlertThreshold(warning=70, critical=90))


class DingtalkConfig(BaseModel):
    enabled: bool = False
    webhook_url: str = ""
    secret: str = ""
    mention_all: bool = False
    mention_mobiles: List[str] = []


class CollectionConfig(BaseModel):
    cron_expression: str = "0 8 * * *"
    timeout_seconds: int = 60
    retry_count: int = 2


class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    cors_origins: List[str] = ["*"]


class DatabaseConfig(BaseModel):
    path: str = "./monitoring.db"
    retention_days: int = 30


class ExcelConfig(BaseModel):
    output_dir: str = "/root/ops_monitor/"
    filename_pattern: str = "Server_Report_{date}.xlsx"
    auto_generate: bool = True


class ServersConfig(BaseModel):
    groups: Dict[str, List[str]] = {"all_linux": [], "windows": []}
    priority_list: List[ServerConfig] = []


class Settings(BaseModel):
    servers: ServersConfig = ServersConfig()
    alert_thresholds: AlertThresholdsConfig = AlertThresholdsConfig()
    dingtalk: DingtalkConfig = DingtalkConfig()
    collection: CollectionConfig = CollectionConfig()
    api: APIConfig = APIConfig()
    database: DatabaseConfig = DatabaseConfig()
    excel: ExcelConfig = ExcelConfig()


class ConfigLoader:
    _instance: Optional["ConfigLoader"] = None
    _config: Optional[Settings] = None
    _config_path: Path = Path("config.yml")
    _last_modified: float = 0

    def __new__(cls, config_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self._config_path = Path(config_path)

    def load(self) -> Settings:
        if self._config is None or self._is_config_changed():
            self._config = self._load_from_file()
            self._last_modified = self._config_path.stat().st_mtime
        return self._config

    def _is_config_changed(self) -> bool:
        try:
            current_mtime = self._config_path.stat().st_mtime
            return current_mtime > self._last_modified
        except Exception:
            return False

    def _load_from_file(self) -> Settings:
        if not self._config_path.exists():
            print(f"⚠️ 配置文件不存在: {self._config_path}，使用默认配置")
            return Settings()

        with open(self._config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f) or {}

        return Settings(**raw_config)

    def reload(self) -> Settings:
        self._config = None
        return self.load()

    def get_server_groups(self) -> Dict[str, List[str]]:
        config = self.load()
        return config.servers.groups

    def get_priority_list(self) -> List[ServerConfig]:
        config = self.load()
        return config.servers.priority_list

    def get_alert_thresholds(self) -> AlertThresholdsConfig:
        config = self.load()
        return config.alert_thresholds

    def get_dingtalk_config(self) -> DingtalkConfig:
        config = self.load()
        return config.dingtalk


config_loader = ConfigLoader()
