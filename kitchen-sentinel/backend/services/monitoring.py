"""监测领域服务。

这里集中处理设备状态、遥测幂等、报警生命周期、控制命令和审计，
HTTP 路由只负责参数解析与权限依赖，便于未来接入真实硬件或云端消息队列。
"""

from datetime import timedelta, timezone
from uuid import uuid4
from sqlalchemy import select
from backend.models import Device, Telemetry, Alarm, Command, RuleConfig, AuditLog, AuthSession, utcnow
from backend.domain.rules import DEFAULT_RULES, evaluate


def stamp(value):
    """把数据库时间转换为前端统一理解的 UTC ISO 字符串。"""
    return value.isoformat(timespec='seconds') + 'Z' if value else None


def audit(db, actor, action, target='', **detail):
    """追加审计记录；调用方在同一事务提交，避免出现半条操作记录。"""
    db.add(AuditLog(actor=actor, action=action, target=str(target), detail=detail))


def serialize(row):
    """把 ORM 行转换成可直接返回给前端的字典，并过滤敏感列。"""
    excluded = {'password_hash', 'token_hash', 'evaluation'}
    return {c.name: stamp(v) if hasattr(v, 'isoformat') else v
            for c in row.__table__.columns if c.name not in excluded
            for v in [getattr(row, c.name)]}


def rules(db):
    """取得当前规则；配置缺失时给出明确错误，避免出现隐晦的 NoneType 异常。"""

    config = db.get(RuleConfig, 1)
    if config is None:
        raise RuntimeError('规则配置不存在，请先执行 scripts/bootstrap.py 初始化数据库')
    # 兼容早期数据库中缺少新增字段的 JSON 配置，避免维护任务直接崩溃。
    # 只有确实补齐了字段才回写，避免每个查询请求都产生一次无意义的 UPDATE。
    merged = {**DEFAULT_RULES, **(config.values or {})}
    if merged != config.values:
        config.values = merged
    return config


def append_event(alarm, message):
    """以追加方式保存报警时间线，避免原列表被原地修改造成 ORM 不识别。"""
    alarm.timeline = [*alarm.timeline, {'at': stamp(utcnow()), 'message': message}]


def sync_alarm(db, device, kind, active, message, evidence=None):
    """同步单个报警类型的触发或恢复状态。"""
    alarm = db.scalar(select(Alarm).where(Alarm.device_id == device.id, Alarm.kind == kind,
                                         Alarm.status == 'active').order_by(Alarm.id.desc()))
    if active and alarm is None:
        alarm = Alarm(device_id=device.id, kind=kind, severity='critical' if kind in ('gas', 'fire') else 'warning',
                      message=message, timeline=[{'at': stamp(utcnow()), 'message': message}], evidence=evidence or {})
        db.add(alarm)
        db.flush()
        audit(db, 'system', 'alarm.trigger', alarm.id, device_id=device.id, kind=kind)
    elif not active and alarm:
        alarm.status, alarm.recovered_at = 'recovered', utcnow()
        append_event(alarm, '触发条件已恢复；人工确认状态独立保留，阀门不自动重开')
    return alarm


def ingest(db, device_id, packet):
    """处理一次设备上报：去重、落库、更新在线状态并复核报警。"""
    # 设备上报是幂等入口：先按设备锁住当前状态，再判断序号，避免重试造成重复样本。
    device = db.scalar(select(Device).where(Device.id == device_id).with_for_update())
    if device is None:
        raise ValueError(f'设备不存在：{device_id}')
    duplicate = db.scalar(select(Telemetry.id).where(Telemetry.device_id == device_id,
        Telemetry.boot_id == packet.boot_id, Telemetry.sequence == packet.sequence))
    if duplicate:
        return {'accepted': True, 'duplicate': True, 'sample_id': duplicate}
    data = packet.model_dump(exclude={'actuators'})
    data['sampled_at'] = packet.sampled_at.astimezone(timezone.utc).replace(tzinfo=None)
    telemetry = Telemetry(device_id=device_id, **data)
    db.add(telemetry)
    db.flush()
    # 迟到数据仍保存，便于审计，但不能倒退当前状态，也不能刷新在线时间。
    latest = device.latest or {}
    previous_time = latest.get('sampled_at', '')
    fresh = (utcnow() - data['sampled_at']).total_seconds() <= 30
    if not fresh or (previous_time and stamp(data['sampled_at']) < previous_time):
        return {'accepted': True, 'duplicate': False, 'historical': True, 'sample_id': telemetry.id}
    device.last_seen = utcnow()
    device.latest = {**packet.model_dump(mode='json', exclude={'actuators'}), 'sampled_at': stamp(data['sampled_at'])}
    device.actuators = packet.actuators
    config = rules(db)
    state, active = evaluate(packet.model_dump(), config.values, device.evaluation or {}, utcnow().timestamp())
    device.evaluation = state
    messages = {'gas': '燃气相对指标持续超过演示阈值', 'fire': '烟雾、温度或火焰触发火灾报警规则',
                'sensor_fault': '传感器数据无效或缺失'}
    for kind, message in messages.items():
        sync_alarm(db, device, kind, kind in active, message,
                   {'sample': device.latest, 'rules_revision': config.revision, 'rules': config.values,
                    'source': device.source})
    sync_alarm(db, device, 'offline', False, '')
    return {'accepted': True, 'duplicate': False, 'sample_id': telemetry.id, 'alarms': sorted(active)}


def maintenance(db):
    """后台周期任务：标记离线设备并关闭超时控制命令。"""
    now = utcnow()
    config = rules(db)
    # 维护任务每两秒运行一次；批量上限避免历史数据异常或大量过期会话拖住事务。
    maintenance_batch = 1000
    # 会话过期后仍需从数据库删除，避免长期演示或部署运行造成无界增长。
    for session in db.scalars(select(AuthSession).where(AuthSession.expires_at < now).limit(maintenance_batch)):
        db.delete(session)
    for device in db.scalars(select(Device).with_for_update().limit(maintenance_batch)):
        if device.last_seen and (now - device.last_seen).total_seconds() > config.values['offline_seconds']:
            sync_alarm(db, device, 'offline', True, '设备超过心跳时限；当前读数为最后一次上报')
    for command in db.scalars(select(Command).where(Command.status.in_(['pending', 'dispatched']),
                                                    Command.expires_at < now)
                              .order_by(Command.expires_at)
                              .limit(maintenance_batch)
                              .with_for_update()):
        command.status, command.completed_at, command.result = 'timeout', now, '设备未在时限内确认执行'
        audit(db, 'system', 'command.timeout', command.id)


def create_command(db, device_id, action, actor, key):
    """创建幂等控制命令；同一业务键重复提交时返回原命令。"""
    # 设备行锁把“检查幂等键”和“创建命令”放在同一临界区，避免双击产生两条控制命令。
    db.scalar(select(Device).where(Device.id == device_id).with_for_update())
    existing = db.scalar(select(Command).where(Command.idempotency_key == key))
    if existing:
        if existing.device_id != device_id or existing.action != action:
            from fastapi import HTTPException
            raise HTTPException(409, '幂等键已经用于另一条命令')
        return existing
    cmd = Command(id=str(uuid4()), device_id=device_id, action=action, requested_by=actor,
                  idempotency_key=key, expires_at=utcnow() + timedelta(seconds=rules(db).values['command_timeout_seconds']))
    db.add(cmd)
    audit(db, actor, 'command.create', cmd.id, action_name=action, device_id=device_id)
    db.flush()
    return cmd


def snapshot(db):
    """生成总览页面所需的聚合快照。"""
    config = rules(db)
    devices = []
    for d in db.scalars(select(Device).order_by(Device.id)):
        item = serialize(d)
        item['online'] = bool(d.last_seen and (utcnow() - d.last_seen).total_seconds() <= config.values['offline_seconds'])
        devices.append(item)
    alarms = [serialize(a) for a in db.scalars(select(Alarm).order_by(Alarm.id.desc()).limit(100))]
    commands = [serialize(c) for c in db.scalars(select(Command).order_by(Command.created_at.desc()).limit(50))]
    return {'server_time': stamp(utcnow()), 'devices': devices, 'alarms': alarms, 'commands': commands,
            'rules': {**config.values, 'revision': config.revision},
            'stats': {'devices': len(devices), 'online': sum(d['online'] for d in devices),
                      'active_alarms': sum(a['status'] == 'active' for a in alarms),
                      'pending_commands': sum(c['status'] in ('pending', 'dispatched') for c in commands)}}
