"""文件职责：统一应用配置。
主要功能：定位项目目录，读取环境变量并构造数据库连接配置，缓存进程配置。
技术栈：Python、Pydantic Settings、SQLAlchemy URL、lru_cache。
模块联动：db 创建连接，main 设置来源白名单，网关和初始化脚本读取各自配置；密钥不返回页面。
编写/修改日期（日志对应）：2026-09-11。
"""

from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# 所有运行时文件都以项目根目录为基准，而不是以当前 PowerShell 目录为基准。
# 这样从工作区上级目录启动服务时，.env、dist 和 .runtime 仍能被正确找到。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROOT = PROJECT_ROOT  # 兼容现有模块引用；新代码优先使用 PROJECT_ROOT。


class Settings(BaseSettings):
    """本地部署所需的最小配置集合。
    编写/修改日期（日志对应）：2026-09-11。
    """

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / '.env', extra='ignore')
    app_env: str = 'development'
    db_host: str = '127.0.0.1'
    db_port: int = 3306
    db_user: str = 'root'
    db_password: str = ''
    db_name: str = 'kitchen_sentinel'
    auth_secret: str = ''
    admin_username: str = 'admin'
    admin_password: str = ''
    device_token: str = ''
    # 日志对应：2026-09-30 设备接入鉴权。硬件令牌独立，避免与模拟器共用节点身份。
    hardware_device_token: str = ''
    cookie_secure: bool = False
    allowed_origins: str = 'http://127.0.0.1:8000'
    model_base_url: str = ''
    model_api_key: str = ''
    model_name: str = ''

    @property
    def database_url(self):
        """构造 SQLAlchemy URL；密码交给驱动处理，避免手工拼接特殊字符出错。
        编写/修改日期（日志对应）：2026-09-11。
        """
        return URL.create('mysql+pymysql', username=self.db_user, password=self.db_password,
                          host=self.db_host, port=self.db_port, database=self.db_name,
                          query={'charset': 'utf8mb4'})

@lru_cache
def settings():
    """返回进程级配置单例，避免每个请求反复读取环境文件。
    编写/修改日期（日志对应）：2026-09-11。
    """
    return Settings()
