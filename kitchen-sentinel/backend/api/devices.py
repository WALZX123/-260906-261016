"""设备协议 v1：遥测上报、控制拉取和命令回执。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from backend.api.dependencies import device_auth
from backend.core.db import get_db
from backend.models import Command, Device, utcnow
from backend.schemas import SampleInput, CommandResult
from backend.services.monitoring import ingest, rules, serialize, audit

router = APIRouter(prefix='/ingest/devices/{device_id}', tags=['设备协议 v1'])


@router.post('/telemetry')
def telemetry(device_id: str, packet: SampleInput, device=Depends(device_auth), db=Depends(get_db)):
    """接收设备数据；业务层负责去重、状态更新和报警同步。"""
    return ingest(db, device_id, packet)


@router.get('/control')
def control(device_id: str, device=Depends(device_auth), db=Depends(get_db)):
    """设备轮询规则和待执行命令，并将命令标记为已下发。"""
    device = db.scalar(select(Device).where(Device.id == device_id).with_for_update())
    pending = list(db.scalars(select(Command).where(Command.device_id == device_id,
                              Command.status.in_(['pending', 'dispatched']), Command.expires_at >= utcnow())
                             .order_by(Command.created_at)
                             .limit(100)))
    for cmd in pending:
        cmd.status = 'dispatched'
    # 一次最多下发 100 条，避免设备长期离线后集中恢复造成超大响应和长事务。
    config = rules(db)
    return {'rules': config.values, 'rules_revision': config.revision,
            'scenario': device.scenario, 'scenario_revision': device.scenario_revision,
            'commands': [serialize(c) for c in pending]}


@router.post('/commands/{command_id}/result')
def result(device_id: str, command_id: str, data: CommandResult, device=Depends(device_auth), db=Depends(get_db)):
    """接收设备回执；已完成命令重复回执时返回原状态以保持幂等。"""
    command = db.scalar(select(Command).where(Command.id == command_id).with_for_update())
    if not command or command.device_id != device_id:
        raise HTTPException(404, '命令不存在')
    if command.status in ('succeeded', 'failed'):
        return serialize(command)
    if command.expires_at < utcnow() or command.status == 'timeout':
        raise HTTPException(409, '命令已过期，不接受迟到的成功回执')
    command.status = 'succeeded' if data.success else 'failed'
    command.result = data.message
    command.completed_at = utcnow()
    audit(db, device_id, 'command.result', command.id, status=command.status, result=data.message)
    return serialize(command)
