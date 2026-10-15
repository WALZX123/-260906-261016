"""文件职责：PC 管理平台业务接口。
主要功能：查询总览与历史、导出 CSV，处理报警确认和现场处置、控制命令、规则及审计。
技术栈：FastAPI、SQLAlchemy、Pydantic、HTTPX、CSV。
模块联动：对接 React 页面、monitoring 业务服务和数据库；模型服务只生成摘要，不改变保护输出。
编写/修改日期（日志对应）：2026-10-05；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
"""

import csv
import io
import json
from typing import Literal
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select, text, case
from backend.core.config import settings
from backend.core.db import get_db
from backend.api.dependencies import current_user, operator, admin
from backend.models import Device, Telemetry, Alarm, RuleConfig, AuditLog, utcnow
from backend.schemas import CommandInput, RuleInput, NoteInput, ScenarioInput
from backend.services.monitoring import snapshot, serialize, create_command, audit, append_event, rules
from scripts.instance import APP_VERSION

router = APIRouter(tags=['监测与管理'])


def require_device(db, device_id):
    """统一校验设备存在，避免每个路由重复编写相同分支。
    编写/修改日期（日志对应）：2026-10-05。
    """
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, '设备不存在')
    return device


@router.get('/snapshot')
def get_snapshot(scope: Literal['hardware', 'simulated', 'all'] = 'hardware',
                 user=Depends(current_user), db=Depends(get_db, scope='function')):
    """返回首页总览数据。
    编写/修改日期（日志对应）：2026-10-05。
    """
    return snapshot(db, scope)


@router.get('/telemetry')
def history(device_id: str | None = None, limit: int = Query(120, ge=1, le=5000),
            start: datetime | None = None, end: datetime | None = None,
            user=Depends(current_user), db=Depends(get_db, scope='function')):
    """查询历史遥测；时间参数必须带时区并在入库时统一转 UTC。
    编写/修改日期（日志对应）：2026-10-05。
    """
    # 日志对应：2026-10-01 历史数据查询。未指定设备时与总览一样优先选实物节点。
    if device_id is None:
        device_id = db.scalar(select(Device.id).order_by(case((Device.source == 'hardware', 0), else_=1), Device.id))
        if device_id is None:
            raise HTTPException(404, '尚未注册设备')
    require_device(db, device_id)
    query = select(Telemetry).where(Telemetry.device_id == device_id)
    for value in (start, end):
        if value and value.tzinfo is None:
            raise HTTPException(422, '查询时间必须包含时区')
    if start and end and start > end:
        raise HTTPException(422, '开始时间不能晚于结束时间')
    if start:
        query = query.where(Telemetry.received_at >= start.astimezone(timezone.utc).replace(tzinfo=None))
    if end:
        query = query.where(Telemetry.received_at <= end.astimezone(timezone.utc).replace(tzinfo=None))
    return [serialize(x) for x in reversed(list(db.scalars(query.order_by(Telemetry.id.desc()).limit(limit))))]


@router.get('/telemetry/export')
def export(device_id: str | None = None, start: datetime | None = None, end: datetime | None = None,
           user=Depends(current_user), db=Depends(get_db, scope='function')):
    """导出与历史查询相同口径的 CSV，限制最大行数避免一次请求耗尽内存。
    编写/修改日期（日志对应）：2026-10-05。
    """
    rows = history(device_id, 5000, start, end, user, db)
    stream = io.StringIO()
    columns = ['id', 'device_id', 'sampled_at', 'received_at', 'gas', 'smoke', 'temperature', 'flame', 'valid', 'local_alarm', 'monitoring_enabled', 'test_scenario', 'transport']
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    return Response('\ufeff' + stream.getvalue(), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename="telemetry.csv"', 'X-Export-Limit': '5000'})


@router.post('/devices/{device_id}/commands', status_code=201)
def command(device_id: str, data: CommandInput, user=Depends(operator), db=Depends(get_db, scope='function')):
    """创建控制命令，实际执行由设备下一次轮询完成。
    编写/修改日期（日志对应）：2026-10-05。
    """
    require_device(db, device_id)
    return serialize(create_command(db, device_id, data.action, user.username, user.username + ':' + data.idempotency_key))


@router.post('/devices/{device_id}/scenario')
def scenario(device_id: str, data: ScenarioInput, user=Depends(operator), db=Depends(get_db, scope='function')):
    """切换模拟设备场景；真实设备不允许使用该演示接口。
    编写/修改日期（日志对应）：2026-10-05。
    """
    device = db.scalar(select(Device).where(Device.id == device_id).with_for_update())
    if not device or device.source != 'simulated':
        raise HTTPException(400, '场景控制只适用于模拟设备')
    device.scenario, device.scenario_revision = data.scenario, device.scenario_revision + 1
    audit(db, user.username, 'simulation.scenario', device_id, scenario=data.scenario)
    return {'scenario': device.scenario, 'revision': device.scenario_revision}


@router.get('/alarms')
def alarms(status: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
           scope: Literal['hardware', 'simulated', 'all'] = 'hardware',
           before_id: int | None = None,
           user=Depends(current_user), db=Depends(get_db, scope='function')):
    """分页查询报警记录。
    编写/修改日期（日志对应）：2026-10-05。
    """
    query = select(Alarm).join(Device, Device.id == Alarm.device_id)
    if scope != 'all':
        query = query.where(Device.source == scope)
    if status:
        query = query.where(Alarm.status == status)
    if before_id is not None:
        query = query.where(Alarm.id < before_id)
    return [serialize(a) for a in db.scalars(query.order_by(Alarm.id.desc()).offset(offset).limit(limit))]


@router.post('/alarms/{alarm_id}/acknowledge')
def acknowledge(alarm_id: int, data: NoteInput, user=Depends(operator), db=Depends(get_db, scope='function')):
    """修改日期（对应实习日志）：2026-10-05。人工确认单独留人名、时间与说明，自动恢复不能代办。
    """
    alarm = db.scalar(select(Alarm).where(Alarm.id == alarm_id).with_for_update())
    if not alarm:
        raise HTTPException(404, '报警不存在')
    if not alarm.acknowledged_at:
        alarm.acknowledged_at, alarm.acknowledged_by = utcnow(), user.username
        append_event(alarm, f'{user.username} 确认报警：{data.note}')
        audit(db, user.username, 'alarm.acknowledge', alarm_id, note=data.note)
    return serialize(alarm)


@router.post('/alarms/{alarm_id}/notes')
def add_note(alarm_id: int, data: NoteInput, user=Depends(operator), db=Depends(get_db, scope='function')):
    """向报警时间线追加人工备注。
    编写/修改日期（日志对应）：2026-10-05。
    """
    alarm = db.scalar(select(Alarm).where(Alarm.id == alarm_id).with_for_update())
    if not alarm:
        raise HTTPException(404, '报警不存在')
    append_event(alarm, f'{user.username} 备注：{data.note}')
    audit(db, user.username, 'alarm.note', alarm_id)
    return serialize(alarm)


@router.post('/alarms/{alarm_id}/resolve')
def resolve_alarm(alarm_id: int, data: NoteInput, user=Depends(operator), db=Depends(get_db, scope='function')):
    """日志对应：2026-10-03。记录人工现场核查；确认、信号恢复、处置完成互不替代。
    """
    alarm = db.scalar(select(Alarm).where(Alarm.id == alarm_id).with_for_update())
    if not alarm:
        raise HTTPException(404, '报警不存在')
    if alarm.status == 'active':
        raise HTTPException(409, '触发条件仍在持续，不能标记处置完成')
    if not alarm.acknowledged_at:
        raise HTTPException(409, '请先确认已知悉报警')
    from backend.domain.response import response_view
    response = response_view(alarm)
    if not response.get('resolution'):
        response = {**response, 'manual_required': False,
                    'resolution': {'at': utcnow().isoformat() + 'Z', 'by': user.username, 'note': data.note}}
        alarm.evidence = {**(alarm.evidence or {}), 'response': response}
        append_event(alarm, f'{user.username} 完成人工现场核查：{data.note}；未下发开阀命令')
        audit(db, user.username, 'alarm.resolve', alarm_id)
    return serialize(alarm)


@router.post('/alarms/{alarm_id}/escalate')
def escalate_alarm(alarm_id: int, data: NoteInput, user=Depends(operator), db=Depends(get_db, scope='function')):
    """日志对应：2026-10-03。现场观察到执行异常时升级人工，不能把输出寄存器当实际动作。
    """
    alarm = db.scalar(select(Alarm).where(Alarm.id == alarm_id).with_for_update())
    if not alarm:
        raise HTTPException(404, '报警不存在')
    from backend.domain.response import response_view
    response = response_view(alarm)
    reasons = list(dict.fromkeys([*response.get('reasons', []), 'onsite_issue']))
    alarm.evidence = {**(alarm.evidence or {}), 'response': {
        **response, 'manual_required': True, 'reasons': reasons, 'resolution': None}}
    append_event(alarm, f'{user.username} 报告现场异常，转人工处置：{data.note}')
    audit(db, user.username, 'alarm.escalate', alarm_id, note=data.note)
    return serialize(alarm)


@router.post('/alarms/{alarm_id}/analysis')
def analysis(alarm_id: int, use_model: bool = False, user=Depends(operator), db=Depends(get_db, scope='function')):
    """生成本地规则摘要，可选调用外部模型，但不允许模型改变控制状态。
    编写/修改日期（日志对应）：2026-10-05。
    """
    alarm = db.get(Alarm, alarm_id)
    if not alarm:
        raise HTTPException(404, '报警不存在')
    values = list(db.scalars(select(Telemetry).where(Telemetry.device_id == alarm.device_id,
        Telemetry.received_at <= (alarm.recovered_at or utcnow()), Telemetry.received_at >= alarm.started_at)
        .order_by(Telemetry.id.desc()).limit(120)))
    # 日志对应：2026-10-03 看板接口。摘要按记录中的设备来源描述，避免把实物数据叫作模拟数据。
    device = db.get(Device, alarm.device_id)
    hardware = device is not None and device.source == 'hardware'
    source_note = ('STM32 实物测试数据，传感器和报警阈值尚未标定'
                   if hardware else '设备模拟器数据，用于验证软件流程')
    # 默认先给出本地规则摘要，模型接口不可用时仍保留事件说明。
    result = {'provider': 'rules', 'generated_at': utcnow().isoformat() + 'Z',
              'summary': f'{alarm.message}。本次采样来源为{source_note}。',
              'sample_count': len(values),
              'peak_gas': max((x.gas for x in values if x.gas is not None), default=None),
              'peak_temperature': max((x.temperature for x in values if x.temperature is not None), default=None),
              'limitations': '相对指标未经实物标定，无法由此确认气体种类或真实事故；分析不改变报警与联动。'}
    config = settings()
    if use_model:
        if not (config.model_api_key and config.model_base_url and config.model_name):
            raise HTTPException(409, '尚未配置模型服务，可先使用规则摘要')
        prompt = ('你是监测事件摘要助手。输入来源：' + source_note +
                  '。只解释已知证据和不确定性，不推断确定气源，不下发控制命令，不建议重开阀门。用中文简短分析：' +
                  json.dumps(result, ensure_ascii=False))
        try:
            response = httpx.post(config.model_base_url.rstrip('/') + '/chat/completions',
                headers={'Authorization': f'Bearer {config.model_api_key}'}, timeout=25,
                json={'model': config.model_name, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.2})
            response.raise_for_status()
            result['summary'] = response.json()['choices'][0]['message']['content'][:6000]
            result['provider'] = config.model_name
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            raise HTTPException(502, '模型服务暂不可用；本地监测与规则摘要不受影响')
    alarm.analysis = result
    audit(db, user.username, 'alarm.analyze', alarm_id, provider=result['provider'])
    return result


@router.put('/rules')
def update_rules(data: RuleInput, user=Depends(admin), db=Depends(get_db, scope='function')):
    """使用版本号做乐观锁，防止两个管理员覆盖彼此的规则修改。
    编写/修改日期（日志对应）：2026-10-05。
    """
    config = db.scalar(select(RuleConfig).where(RuleConfig.id == 1).with_for_update())
    if config is None:
        raise HTTPException(503, '规则配置不存在，请先初始化数据库')
    if data.revision != config.revision:
        raise HTTPException(409, '配置已被其他操作更新，请刷新后重试')
    old = config.values
    config.values = data.model_dump(exclude={'revision'})
    config.revision += 1
    config.updated_at = utcnow()
    audit(db, user.username, 'rules.update', config.revision, before=old, after=config.values)
    return {**config.values, 'revision': config.revision}


@router.get('/audit')
def logs(limit: int = Query(100, ge=1, le=500), user=Depends(admin), db=Depends(get_db, scope='function')):
    """查询管理员可见的操作审计。
    编写/修改日期（日志对应）：2026-10-05。
    """
    return [serialize(a) for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit))]


@router.get('/system')
def system(user=Depends(current_user), db=Depends(get_db, scope='function')):
    """返回部署、数据库、规则和数据口径信息。
    编写/修改日期（日志对应）：2026-10-05。
    """
    db.execute(text('SELECT 1'))
    # 日志对应：2026-10-03 看板接口。按已注册设备和实际最新传输方式报告系统状态。
    hardware = db.scalar(select(Device).where(Device.source == 'hardware').order_by(Device.id))
    hardware_status = '设备模拟器，尚未注册实物节点'
    if hardware is not None:
        transport = (hardware.latest or {}).get('transport')
        hardware_status = ('STM32 实物采样已接入（SWD 调试器）' if transport == 'swd'
                           else 'STM32 实物节点已注册，等待通信验证')
    return {'version': APP_VERSION, 'database': 'MySQL', 'database_connected': True,
            'deployment': '本机部署', 'hardware': hardware_status,
            'model_configured': bool(settings().model_api_key and settings().model_base_url and settings().model_name),
            'rules_revision': rules(db).revision, 'protocol': 'kitchen.v1',
            'export_limit': 5000, 'data_unit': '燃气/烟雾为 0–100 相对指标；温度为 °C'}
