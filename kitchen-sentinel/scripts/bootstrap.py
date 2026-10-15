"""文件职责：本地环境与数据库初始化入口。
主要功能：准备配置、创建数据库、执行迁移、幂等写入管理员、设备和规则。
技术栈：Python、SQLAlchemy、Alembic、随机凭据、文件持久化。
模块联动：start.py 调用；复用 runtime 和 core 配置；账号仅保存在本机运行目录，原有业务数据不被清空。
编写/修改日期（日志对应）：2026-09-11。
"""
import os
import re
import secrets
import subprocess
import sys

try:
    from scripts.runtime import PROJECT_ROOT, ensure_project_python
except ModuleNotFoundError:  # 通过绝对文件路径直接执行时使用脚本目录导入。
    from runtime import PROJECT_ROOT, ensure_project_python

ensure_project_python()
ROOT = PROJECT_ROOT
sys.path.insert(0, str(ROOT))


def prepare_env():
    """首次运行时创建 .env，并为占位密钥生成随机值。
    编写/修改日期（日志对应）：2026-09-11。
    """
    path = ROOT / '.env'
    if not path.exists():
        path.write_text((ROOT / '.env.example').read_text(encoding='utf-8'), encoding='utf-8')
    content = path.read_text(encoding='utf-8')
    for name in ('AUTH_SECRET', 'ADMIN_PASSWORD', 'DEVICE_TOKEN'):
        content = content.replace(f'{name}=GENERATE_WITH_SETUP', f'{name}={secrets.token_urlsafe(24)}')
    path.write_text(content, encoding='utf-8')


def main():
    """完成数据库创建、迁移和最小演示数据初始化。
    编写/修改日期（日志对应）：2026-09-11。
    """
    os.chdir(ROOT)
    prepare_env()
    from backend.core.config import settings
    from backend.core.security import hash_password, digest
    from backend.core.db import SessionLocal
    from backend.models import User, Device, RuleConfig
    from backend.domain.rules import DEFAULT_RULES
    from sqlalchemy import create_engine, text, select
    cfg = settings()
    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]{0,63}', cfg.db_name):
        raise SystemExit('Invalid project database name')
    if cfg.db_password == 'PLEASE_FILL_LOCALLY':
        raise SystemExit('Please fill DB_PASSWORD in .env locally first.')
    admin_engine = create_engine(cfg.database_url._replace(database=None))
    try:
        with admin_engine.begin() as conn:
            conn.execute(text(f'CREATE DATABASE IF NOT EXISTS `{cfg.db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'))
    except Exception:
        raise SystemExit('MySQL connection/setup failed. Check .env and database privileges; password was not logged.')
    # --create-only 只建库，不写入应用表；完整启动时再执行迁移和演示种子数据。
    if '--create-only' in sys.argv:
        print('Project database is ready.')
        return
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], check=True)
    with SessionLocal.begin() as db:
        if not db.scalar(select(User).where(User.username == cfg.admin_username)):
            db.add(User(username=cfg.admin_username, password_hash=hash_password(cfg.admin_password), role='admin'))
        if not db.get(Device, 'kitchen-001'):
            db.add(Device(id='kitchen-001', name='家庭厨房实验节点', location='实验演示区 · 厨房 01',
                          token_hash=digest(cfg.device_token), source='simulated'))
        if not db.get(RuleConfig, 1):
            db.add(RuleConfig(id=1, revision=1, values=DEFAULT_RULES.copy()))
    access = ROOT / '.runtime' / 'access.txt'
    access.parent.mkdir(exist_ok=True)
    access.write_text(f'Local application login (keep private)\nURL: http://127.0.0.1:8000\nUsername: {cfg.admin_username}\nPassword: {cfg.admin_password}\n', encoding='utf-8')
    print('Database migrated and seeded. Local login is in .runtime/access.txt (not printed).')


if __name__ == '__main__':
    main()
