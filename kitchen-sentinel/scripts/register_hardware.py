"""文件职责：实物设备身份注册工具。
主要功能：为 STM32 生成或复用独立令牌，幂等维护设备资料。
技术栈：Python secrets、SQLAlchemy、摘要身份认证。
模块联动：start.py 在采集前调用；core 配置和 .env 保存本机令牌，Device 保存摘要，硬件与模拟器数据分开。
编写/修改日期（日志对应）：2026-09-30。
"""
from __future__ import annotations

import secrets

from sqlalchemy import select

from backend.core.config import PROJECT_ROOT, settings
from backend.core.db import SessionLocal
from backend.core.security import digest
from backend.models import Device
from backend.services.monitoring import audit

DEVICE_ID = 'stm32-001'


def main() -> None:
    """首次生成本机令牌；重复执行更新同一硬件节点，不输出令牌内容。
    编写/修改日期（日志对应）：2026-09-30。
    """
    cfg = settings()
    if not cfg.hardware_device_token:
        # 只在本机 .env 保存原始令牌，数据库保存摘要；日志中不打印认证信息。
        env = PROJECT_ROOT / '.env'
        content = env.read_text(encoding='utf-8')
        token = secrets.token_urlsafe(32)
        lines = [line for line in content.splitlines() if not line.startswith('HARDWARE_DEVICE_TOKEN=')]
        env.write_text('\n'.join([*lines, f'HARDWARE_DEVICE_TOKEN={token}', '']), encoding='utf-8')
        settings.cache_clear()
        cfg = settings()
    with SessionLocal.begin() as db:
        device = db.scalar(select(Device).where(Device.id == DEVICE_ID).with_for_update())
        # 日志对应：2026-09-26。身份被其他来源占用时停止，防止把模拟数据改名为硬件数据。
        if device is not None and device.source != 'hardware':
            raise RuntimeError('stm32-001 is already registered with a different data source')
        if device is None:
            device = Device(id=DEVICE_ID, name='STM32 厨房监测节点', location='硬件实验台', source='hardware',
                            token_hash=digest(cfg.hardware_device_token), firmware='awaiting-telemetry')
            db.add(device)
            audit(db, 'local-setup', 'hardware.register', DEVICE_ID, source='hardware')
        else:
            # 日志对应：2026-09-30。重复注册保留实机上报的版本，不能用待编译版本覆盖。
            device.token_hash = digest(cfg.hardware_device_token)
            # 日志对应：2026-10-03。只更新早期默认名称，用户自定义的设备名称继续保留。
            if device.name == 'STM32 实物测试节点':
                device.name = 'STM32 厨房监测节点'
                audit(db, 'local-setup', 'hardware.rename', DEVICE_ID, name=device.name)
    print('Hardware node stm32-001 is ready; its independent token stays in the local .env file.')


if __name__ == '__main__':
    main()
