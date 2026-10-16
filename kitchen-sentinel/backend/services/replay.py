"""文件职责：离线采样及报警回放。
功能：按启动号/序号幂等归档，重建断网期间报警；补传不回退当前状态、不触发控制。
技术栈：SQLAlchemy事务、JSON回放游标；关联设备backfill API、Telemetry、Alarm。
编写/修改日期（日志对应）：2026-10-16（供气演示）；2026-10-01、2026-10-15。
"""
from datetime import timezone
from sqlalchemy import select
from backend.models import Device, Telemetry, Alarm, ReplayState
from backend.services.monitoring import append_event


def archive_backfill(db, device_id, packet):
    """锁定设备并先去重，保存采集和接收时间；只有事务提交后网关才能发送ACK。"""
    db.scalar(select(Device).where(Device.id == device_id).with_for_update())
    duplicate = db.scalar(select(Telemetry.id).where(Telemetry.device_id == device_id,
        Telemetry.boot_id == packet.boot_id, Telemetry.sequence == packet.sequence))
    if duplicate:
        return {'accepted': True, 'duplicate': True, 'sample_id': duplicate}
    value = packet.model_dump()
    fields = {k: value[k] for k in ('boot_id', 'sequence', 'gas', 'smoke', 'temperature', 'flame', 'valid', 'local_alarm')}
    when = packet.sampled_at.astimezone(timezone.utc).replace(tzinfo=None)
    context = packet.model_dump(mode='json', include={'monitoring_enabled', 'test_scenario', 'transport', 'raw', 'filtered',
        'firmware', 'io_valid', 'clock_quality', 'device_uptime_ms', 'diagnostics'})
    context['backfilled'] = True
    row = Telemetry(device_id=device_id, sampled_at=when, sample_context=context, **fields)
    db.add(row)
    db.flush()
    state = db.get(ReplayState, (device_id, packet.boot_id))
    if state is None:
        state = ReplayState(device_id=device_id, boot_id=packet.boot_id, sequence=-1, active={})
        db.add(state)
    if packet.sequence <= state.sequence:
        return {'accepted': True, 'historical': True, 'sample_id': row.id}
    active = dict(state.active or {})
    kinds = set()
    if packet.local_alarm in ('gas', 'multiple'):
        kinds.add('gas')
    if packet.local_alarm in ('fire', 'multiple'):
        kinds.add('fire')
    if packet.local_alarm == 'supply_low' or packet.diagnostics.get('supply_low_latched'):
        kinds.add('supply_low')
    if packet.local_alarm == 'sensor_fault':
        kinds.add('sensor_fault')
    for kind in kinds - active.keys():
        alarm = Alarm(device_id=device_id, kind=kind, severity='critical' if kind in ('gas', 'fire') else 'warning',
            status='active', started_at=when, message='离线采样补传：' + {'gas': '燃气指标报警', 'fire': '火灾类信号', 'sensor_fault': '采样故障', 'supply_low': '供气演示低值异常，需人工核查'}[kind],
            timeline=[], evidence={'source': 'hardware', 'backfilled': True, 'test_scenario': packet.test_scenario,
            'sample': packet.model_dump(mode='json'), 'response': {'automatic_status': 'historical_report',
            'manual_required': True, 'reasons': ['offline_replay'], 'actions': [], 'resolution': None,
            'feedback_level': 'historical_control_outputs'}})
        db.add(alarm)
        db.flush()
        append_event(alarm, '根据设备离线存档重建；采集时间见触发字段，接收时间见本时间线；仍待人工确认')
        active[kind] = alarm.id
    for kind in active.keys() - kinds:
        alarm = db.get(Alarm, active[kind])
        if alarm:
            alarm.status, alarm.recovered_at = 'recovered', when
            append_event(alarm, '后续离线样本显示信号恢复；异常记录与人工确认保留')
    state.active = {kind: alarm_id for kind, alarm_id in active.items() if kind in kinds}
    state.sequence = packet.sequence
    return {'accepted': True, 'historical': True, 'sample_id': row.id}


def finish_replay(db, device_id, packet):
    """补传队列清空且当前无对应危险时关闭回放事件；恢复时间作为上界并明确说明。"""
    if packet.diagnostics.get('cache_pending', -1) != 0 or not packet.monitoring_enabled:
        return
    current = {'gas', 'fire'} if packet.local_alarm == 'multiple' else {packet.local_alarm}
    if packet.diagnostics.get('supply_low_latched'):
        current.add('supply_low')
    for state in db.scalars(select(ReplayState).where(ReplayState.device_id == device_id)):
        remaining = dict(state.active or {})
        for kind, alarm_id in list(remaining.items()):
            if kind in current:
                continue
            alarm = db.get(Alarm, alarm_id)
            if alarm and alarm.status == 'active':
                alarm.status = 'recovered'
                alarm.recovered_at = packet.sampled_at.astimezone(timezone.utc).replace(tzinfo=None)
                append_event(alarm, '离线补传已完成，当前信号已恢复；本恢复时间是核验上界，期间准确恢复时刻未知，仍待人工确认')
            remaining.pop(kind)
        state.active = remaining
