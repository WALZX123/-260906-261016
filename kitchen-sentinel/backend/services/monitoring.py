"""文件职责：采样入库、报警和命令的业务编排。
主要功能：遥测去重、状态更新、异常留档、独立人工确认、超时维护、快照聚合与审计。
技术栈：SQLAlchemy ORM、MySQL JSON、规则状态机、UUID。
模块联动：devices 和 platform 调用本服务，rules/response 计算状态，main 周期维护并推送快照；恢复事件仍保留待确认状态。
编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-10-05；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
"""

from datetime import timedelta, timezone
from uuid import uuid4
from sqlalchemy import select, case, func, or_
from backend.models import Device, Telemetry, Alarm, Command, RuleConfig, AuditLog, AuthSession, utcnow
from backend.domain.rules import DEFAULT_RULES, evaluate
from backend.domain.response import evaluate_response, response_view, REASON_LABELS


def stamp(value):
    """把数据库时间转换为前端统一理解的 UTC ISO 字符串。
    编写/修改日期（日志对应）：2026-10-05。
    """
    return value.isoformat(timespec='seconds') + 'Z' if value else None


def audit(db, actor, action, target='', **detail):
    """追加审计记录；调用方在同一事务提交，避免出现半条操作记录。
    编写/修改日期（日志对应）：2026-10-05。
    """
    db.add(AuditLog(actor=actor, action=action, target=str(target), detail=detail))


def serialize(row):
    """把 ORM 行转换成可直接返回给前端的字典，并过滤敏感列。
    编写/修改日期（日志对应）：2026-10-05。
    """
    excluded = {'password_hash', 'token_hash', 'evaluation'}
    result = {c.name: stamp(v) if hasattr(v, 'isoformat') else v
            for c in row.__table__.columns if c.name not in excluded
            for v in [getattr(row, c.name)]}
    if isinstance(row, Telemetry) and row.sample_context:
        result.update(row.sample_context)
    if isinstance(row, Alarm):
        result['response'] = response_view(row)
    return result


def rules(db):
    """取得当前规则；配置缺失时给出明确错误，避免出现隐晦的 NoneType 异常。
    编写/修改日期（日志对应）：2026-10-05。
    """

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
    """以追加方式保存报警时间线，避免原列表被原地修改造成 ORM 不识别。
    编写/修改日期（日志对应）：2026-10-05。
    """
    alarm.timeline = [*alarm.timeline, {'at': stamp(utcnow()), 'message': message}]


def sync_alarm(db, device, kind, active, message, evidence=None):
    """修改日期（对应实习日志）：2026-10-05。所有异常留档，恢复只更新状态，不删除或自动确认。

    输入异常类型及是否持续；新异常写独立事件，恢复只补恢复时间和时间线，确认人及确认时间不由自动流程填写。
    """
    alarm = db.scalar(select(Alarm).where(Alarm.device_id == device.id, Alarm.kind == kind,
                                         Alarm.status == 'active').order_by(Alarm.id.desc()))
    if active and alarm is None:
        alarm = Alarm(device_id=device.id, kind=kind, severity='critical' if kind in ('gas', 'fire') else 'warning',
                      message=message, timeline=[{'at': stamp(utcnow()), 'message': message}], evidence=evidence or {})
        db.add(alarm)
        db.flush()
        audit(db, 'system', 'alarm.trigger', alarm.id, device_id=device.id, kind=kind)
    elif active and alarm and evidence and evidence.get('test_scenario', '') != (alarm.evidence or {}).get('test_scenario', ''):
        # 新真实险情接管演练时立即取消演练标签；同一活动事件仍追加每次场景变化，避免混淆来源。
        sample = evidence.get('sample', {})
        if sample.get('local_alarm') in ('gas', 'fire', 'multiple'):
            scenario = evidence.get('test_scenario', '')
            append_event(alarm, '保护输入切换为：' + (scenario + ' 演练' if scenario else '真实传感器险情，演练已中止'))
            alarm.evidence = {**alarm.evidence, 'test_scenario': scenario,
                              'scenario_history': [*(alarm.evidence or {}).get('scenario_history', []),
                                                   {'at': stamp(utcnow()), 'test_scenario': scenario}]}
    elif not active and alarm:
        alarm.status, alarm.recovered_at = 'recovered', utcnow()
        # 自动处置完成仍需人员确认；已确认的事件保留原确认人和时间，不重复要求确认。
        confirmation = '仍待人工确认' if not alarm.acknowledged_at else '保留已有人工确认'
        append_event(alarm, f'触发条件已恢复；异常记录继续保留，{confirmation}；阀门不自动重开')
    if alarm is not None:
        refresh_response(alarm, device, rules(db).values)
    return alarm


def refresh_response(alarm, device, config, failed=False):
    """日志对应：2026-10-03。自动处置效果与人工确认独立；超时只升级事件，不伪造现场执行。

    调用 domain.response 比对最新采样和输出报告，持久化升级原因；现场处置完成记录独立保留。
    """
    previous = (alarm.evidence or {}).get('response', {})
    response = evaluate_response(alarm.kind, alarm.status == 'active',
        max(0, (utcnow() - alarm.started_at).total_seconds()), device.latest or {}, device.actuators or {},
        config, previous, device.source, failed)
    if response != previous:
        alarm.evidence = {**(alarm.evidence or {}), 'response': response}
        if response['manual_required'] and not previous.get('manual_required'):
            append_event(alarm, '需要人工处置：' + '、'.join(REASON_LABELS.get(r, r) for r in response['reasons']))


def ingest(db, device_id, packet):
    """处理一次设备上报：去重、落库、更新在线状态并复核报警。

    输入会话、设备编号和 SampleInput；按启动编号与序号去重，保存遥测并更新设备、规则状态和报警，返回接收结果。
    编写/修改日期（日志对应）：2026-10-05。
    """
    # 设备上报是幂等入口：先按设备锁住当前状态，再判断序号，避免重试造成重复样本。
    device = db.scalar(select(Device).where(Device.id == device_id).with_for_update())
    if device is None:
        raise ValueError(f'设备不存在：{device_id}')
    duplicate = db.scalar(select(Telemetry.id).where(Telemetry.device_id == device_id,
        Telemetry.boot_id == packet.boot_id, Telemetry.sequence == packet.sequence))
    if duplicate:
        return {'accepted': True, 'duplicate': True, 'sample_id': duplicate}
    # 日志对应：2026-10-01 历史数据存储。原始通道和传输方式保存到最新 JSON 快照；历史列沿用原模型。
    data = packet.model_dump(exclude={'actuators', 'raw', 'filtered', 'disabled_sensors', 'firmware', 'transport', 'io_valid',
                                      'control_capabilities', 'diagnostics', 'monitoring_enabled', 'test_scenario'})
    data['sampled_at'] = packet.sampled_at.astimezone(timezone.utc).replace(tzinfo=None)
    data['sample_context'] = packet.model_dump(mode='json', include={'monitoring_enabled', 'test_scenario', 'transport', 'raw', 'filtered', 'firmware', 'io_valid'})
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
    # 日志对应：2026-09-30。设备信息取已接收的实机状态，不从本地待编译源码推断。
    if device.source == 'hardware' and packet.firmware:
        device.firmware = packet.firmware
    device.latest = {**packet.model_dump(mode='json', exclude={'actuators'}), 'sampled_at': stamp(data['sampled_at'])}
    device.actuators = packet.actuators
    config = rules(db)
    state, active = evaluate(packet.model_dump(), config.values, device.evaluation or {}, utcnow().timestamp())
    device.evaluation = state
    # 日志对应：2026-09-26。硬件缺少温度换算时明确标记待标定，避免把无效量当正常测量。
    messages = {'gas': '燃气相对指标持续超过报警阈值', 'fire': '烟雾、温度或火焰触发火灾报警规则',
                'sensor_fault': '采样尚未标定或存在无效通道' if device.source == 'hardware'
                else '传感器数据无效或缺失'}
    for kind, message in messages.items():
        sync_alarm(db, device, kind, kind in active, message,
                   {'sample': device.latest, 'rules_revision': config.revision, 'rules': config.values,
                    'source': device.source, 'test_scenario': packet.test_scenario})
    sync_alarm(db, device, 'offline', False, '')
    return {'accepted': True, 'duplicate': False, 'sample_id': telemetry.id, 'alarms': sorted(active)}


def maintenance(db):
    """后台周期任务：标记离线设备并关闭超时控制命令。

    由应用后台任务调用，处理过期会话、设备离线、控制超时和自动响应升级；所有修改在调用方事务内提交。
    编写/修改日期（日志对应）：2026-10-05。
    """
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
        record_command_outcome(db, command)
    # 即使后续没有新采样，自动响应超时也必须升级，不能一直显示“正在自动处理”。
    for alarm in db.scalars(select(Alarm).where(Alarm.status == 'active').limit(maintenance_batch)):
        device = db.get(Device, alarm.device_id)
        if device:
            failed = db.scalar(select(Command.id).where(Command.device_id == device.id,
                Command.action == 'close_valve', Command.status == 'failed',
                Command.completed_at >= alarm.started_at).limit(1))
            refresh_response(alarm, device, config.values, failed=bool(failed))


def record_command_outcome(db, command):
    """日志对应：2026-10-12。每次命令失败或超时独立留报警，后续成功只标恢复，不代替人工确认。

    输入已写入最终状态的 Command；失败按命令编号幂等建档，成功仅恢复同设备同动作的旧故障。
    """
    device = db.get(Device, command.device_id)
    if not device:
        return
    if command.status in ('failed', 'timeout'):
        existing = db.scalar(select(Alarm.id).where(Alarm.device_id == device.id, Alarm.kind == 'control_fault',
            Alarm.evidence['command_id'].as_string() == command.id))
        if existing:
            return
        message = f'控制命令 {command.action} ' + ('执行超时' if command.status == 'timeout' else '执行失败')
        alarm = Alarm(device_id=device.id, kind='control_fault', severity='warning', message=message,
            timeline=[{'at': stamp(utcnow()), 'message': message + '：' + (command.result or '无设备说明')}],
            evidence={'command_id': command.id, 'action': command.action, 'result': command.result,
                      'source': device.source, 'test_scenario': (device.latest or {}).get('test_scenario', '')})
        db.add(alarm)
        db.flush()
        refresh_response(alarm, device, rules(db).values, failed=True)
        audit(db, 'system', 'alarm.trigger', alarm.id, device_id=device.id, kind='control_fault')
    elif command.status == 'succeeded':
        for alarm in db.scalars(select(Alarm).where(Alarm.device_id == device.id, Alarm.kind == 'control_fault',
                Alarm.status == 'active', Alarm.evidence['action'].as_string() == command.action)):
            alarm.status, alarm.recovered_at = 'recovered', utcnow()
            append_event(alarm, '后续同类命令收到成功回执；故障记录保留，仍需人工确认和现场核查')
            refresh_response(alarm, device, rules(db).values)


def create_command(db, device_id, action, actor, key):
    """创建幂等控制命令；同一业务键重复提交时返回原命令。

    以设备行锁和幂等键避免重复命令；实物必须在线并声明动作能力，旧固件或不支持的动作返回 409。
    编写/修改日期（日志对应）：2026-10-05。
    """
    # 设备行锁把“检查幂等键”和“创建命令”放在同一临界区，避免双击产生两条控制命令。
    device = db.scalar(select(Device).where(Device.id == device_id).with_for_update())
    # 日志对应：2026-10-02 远程控制。按实际固件能力准入，不能因网页提供按钮就假定设备能执行。
    if device is not None and device.source == 'hardware' and (
        action not in (device.latest or {}).get('control_capabilities', [])
        or not device.last_seen
        or (utcnow() - device.last_seen).total_seconds() > rules(db).values['offline_seconds']
    ):
        from fastapi import HTTPException
        raise HTTPException(409, '设备离线或当前固件尚未上报此动作的执行能力，请检查设备版本和连接')
    if device is not None and device.source == 'simulated' and action not in ('close_valve', 'silence', 'self_test'):
        from fastapi import HTTPException
        raise HTTPException(409, '执行器分项测试只适用于具备执行回执的实物设备')
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


def snapshot(db, scope='all'):
    """生成总览页面所需的聚合快照。

    聚合设备、最近报警、命令和规则，返回 React 总览与 WebSocket 共用的数据结构，不暴露凭据摘要。
    编写/修改日期（日志对应）：2026-10-05。
    """
    config = rules(db)
    devices = []
    # 日志对应：2026-10-03 看板框架。默认总览优先显示实物节点，模拟节点保持独立。
    device_query = select(Device)
    if scope != 'all':
        device_query = device_query.where(Device.source == scope)
    for d in db.scalars(device_query.order_by(case((Device.source == 'hardware', 0), else_=1), Device.id)):
        item = serialize(d)
        item['online'] = bool(d.last_seen and (utcnow() - d.last_seen).total_seconds() <= config.values['offline_seconds'])
        devices.append(item)
    # 日志对应：2026-10-13。正式页面只统计实物；待确认及活动事件优先，防止被新历史挤掉。
    ids = [item['id'] for item in devices]
    alarm_query = select(Alarm).where(Alarm.device_id.in_(ids))
    legacy_manual = or_(Alarm.kind.in_(['fire', 'sensor_fault', 'control_fault']),
                        (Alarm.kind == 'offline') & (Alarm.status == 'active'))
    manual_required = func.coalesce(Alarm.evidence['response']['manual_required'].as_boolean(), legacy_manual).is_(True)
    alarms = [serialize(a) for a in db.scalars(alarm_query.order_by(
        case((Alarm.status == 'active', 0), (manual_required, 1), (Alarm.acknowledged_at.is_(None), 2), else_=3),
        case((Alarm.severity == 'critical', 0), else_=1),
        Alarm.id.desc()).limit(100))]
    commands = [serialize(c) for c in db.scalars(select(Command).where(Command.device_id.in_(ids))
        .order_by(Command.created_at.desc()).limit(50))]
    active_count = db.scalar(select(func.count()).select_from(Alarm).where(
        Alarm.device_id.in_(ids), Alarm.status == 'active'))
    unack_count = db.scalar(select(func.count()).select_from(Alarm).where(
        Alarm.device_id.in_(ids), Alarm.acknowledged_at.is_(None)))
    # JSON 字段在数据库内计数，兼容早期没有 response 的火灾/故障记录，避免每秒加载整张报警表。
    manual_count = db.scalar(select(func.count()).select_from(Alarm).where(Alarm.device_id.in_(ids),
        manual_required))
    pending_count = db.scalar(select(func.count()).select_from(Command).where(Command.device_id.in_(ids),
        Command.status.in_(['pending', 'dispatched'])))
    return {'server_time': utcnow().isoformat(timespec='milliseconds') + 'Z', 'devices': devices, 'alarms': alarms, 'commands': commands,
            'rules': {**config.values, 'revision': config.revision},
            'stats': {'devices': len(devices), 'online': sum(d['online'] for d in devices),
                      'active_alarms': active_count,
                      'unacknowledged_alarms': unack_count,
                      'manual_required_alarms': manual_count,
                      'pending_commands': pending_count}}
