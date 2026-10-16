"""文件职责：完整采样检索、故障统计与周报月报。
主要功能：按采集时间分页检索全部记录、流式导出、聚合主要故障、保存并下载报告。
技术栈：FastAPI、SQLAlchemy聚合、CSV、JSON、DeepSeek；关联Telemetry、Alarm及OperationReport。
编写/修改日期（日志对应）：2026-10-16（工况及提醒持久化）；2026-10-16（供气演示）；2026-10-01、2026-10-08、2026-10-15。
"""
import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select, func, case, or_
from backend.api.dependencies import current_user, operator
from backend.core.db import get_db, SessionLocal
from backend.models import Device, Telemetry, Alarm, OperationReport, utcnow
from backend.services.monitoring import serialize, audit
from backend.services.expert import expert_analysis

router = APIRouter(tags=['数据与运行报告'])
LOCAL = ZoneInfo('Asia/Shanghai')
FAULT_NAMES = {'supply_low': '供气演示低值异常', 'gas': '燃气报警', 'fire': '火灾报警', 'offline': '设备离线',
               'sensor_fault': '传感器故障', 'control_fault': '控制执行异常', 'storage_fault': '采样存档缺口'}


def utc(value):
    """校验浏览器时间含时区，转为数据库使用的无时区UTC。"""
    if value is None:
        return None
    if value.tzinfo is None:
        raise HTTPException(422, '查询时间必须包含时区')
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def sample_query(db, device_id, start=None, end=None, nature='all'):
    """统一采样查询条件，按采集时间检索；分页、统计和导出保持同一口径。"""
    if not db.get(Device, device_id):
        raise HTTPException(404, '设备不存在')
    start, end = utc(start), utc(end)
    if start and end and start >= end:
        raise HTTPException(422, '结束时间必须晚于开始时间')
    query = select(Telemetry).where(Telemetry.device_id == device_id)
    if start:
        query = query.where(Telemetry.sampled_at >= start)
    if end:
        query = query.where(Telemetry.sampled_at < end)
    context = Telemetry.sample_context
    if nature == 'drill':
        query = query.where(context['test_scenario'].as_string().is_not(None), context['test_scenario'].as_string() != '')
    elif nature == 'standby':
        query = query.where(context['monitoring_enabled'].as_boolean().is_(False))
    elif nature == 'backfill':
        query = query.where(context['backfilled'].as_boolean().is_(True))
    elif nature == 'sampling':
        query = query.where(context['monitoring_enabled'].as_boolean().is_(True),
                            or_(context['test_scenario'].as_string().is_(None), context['test_scenario'].as_string() == ''))
    return query


@router.get('/archive/samples')
def samples(device_id: str, start: datetime | None = None, end: datetime | None = None,
            nature: Literal['all', 'sampling', 'drill', 'standby', 'backfill'] = 'all',
            before_id: int | None = None, snapshot_id: int | None = None,
            limit: int = Query(100, ge=1, le=500), user=Depends(current_user), db=Depends(get_db, scope='function')):
    """固定查询快照并按主键游标翻页；新增实时数据不造成旧页跳动或遗漏。"""
    query = sample_query(db, device_id, start, end, nature)
    maximum = db.scalar(select(func.max(Telemetry.id)).where(Telemetry.device_id == device_id)) or 0
    ceiling = min(snapshot_id, maximum) if snapshot_id is not None else maximum
    query = query.where(Telemetry.id <= ceiling)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    if before_id is not None:
        query = query.where(Telemetry.id < before_id)
    rows = list(db.scalars(query.order_by(Telemetry.id.desc()).limit(limit + 1)))
    more = len(rows) > limit
    rows = rows[:limit]
    return {'items': [serialize(row) for row in rows], 'total': total, 'snapshot_id': ceiling,
            'next_before_id': rows[-1].id if more else None, 'has_more': more}


@router.get('/archive/export')
def export_all(device_id: str, start: datetime | None = None, end: datetime | None = None,
               nature: Literal['all', 'sampling', 'drill', 'standby', 'backfill'] = 'all',
               user=Depends(current_user), db=Depends(get_db, scope='function')):
    """导出全部匹配数据，分批读取并固定最大ID；没有静默5000条截断。"""
    sample_query(db, device_id, start, end, nature)
    ceiling = db.scalar(select(func.max(Telemetry.id)).where(Telemetry.device_id == device_id)) or 0

    def chunks():
        """独立只读会话每批1000条；客户端断开时释放连接，避免持有原请求事务。"""
        stream = io.StringIO()
        columns = ['id', 'device_id', 'boot_id', 'sequence', 'sampled_at', 'received_at', 'gas', 'smoke',
                   'temperature', 'flame', 'valid', 'io_valid', 'local_alarm', 'monitoring_enabled', 'test_scenario', 'backfilled', 'clock_quality', 'transport', 'device_uptime_ms', 'raw', 'filtered', 'diagnostics']
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        yield '\ufeff' + stream.getvalue()
        cursor = 0
        with SessionLocal() as session:
            while True:
                query = sample_query(session, device_id, start, end, nature).where(Telemetry.id > cursor, Telemetry.id <= ceiling)
                rows = list(session.scalars(query.order_by(Telemetry.id).limit(1000)))
                if not rows:
                    break
                stream.seek(0)
                stream.truncate()
                for row in rows:
                    value = serialize(row)
                    for name in ('raw', 'filtered', 'diagnostics'):
                        value[name] = json.dumps(value.get(name), ensure_ascii=False)
                    writer.writerow(value)
                yield stream.getvalue()
                cursor = rows[-1].id
    return StreamingResponse(chunks(), media_type='text/csv; charset=utf-8',
                             headers={'Content-Disposition': 'attachment; filename="all-telemetry.csv"'})


def period_bounds(period: str, anchor: date):
    """周报按周一到下周一，月报按自然月；上海本地边界转换成UTC半开区间。"""
    if period == 'weekly':
        first = anchor - timedelta(days=anchor.weekday())
        last = first + timedelta(days=7)
    else:
        first = anchor.replace(day=1)
        last = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return (datetime.combine(first, datetime.min.time(), LOCAL).astimezone(timezone.utc).replace(tzinfo=None),
            datetime.combine(last, datetime.min.time(), LOCAL).astimezone(timezone.utc).replace(tzinfo=None))


def report_facts(db, device_id, start, end):
    """数据库聚合完整统计窗口；模型只接收可核验事实及有界事件摘要，避免抽样冒充总量。"""
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(404, '设备不存在')
    query = select(Telemetry).where(Telemetry.device_id == device_id, Telemetry.sampled_at >= start, Telemetry.sampled_at < end)
    rows = query.subquery()
    stats = db.execute(select(func.count().label('sample_count'), func.max(rows.c.gas).label('peak_gas'),
        func.max(rows.c.smoke).label('peak_smoke'), func.max(rows.c.temperature).label('peak_temperature'),
        func.min(rows.c.sampled_at).label('first_sample'), func.max(rows.c.sampled_at).label('last_sample'))).mappings().one()
    stats = {key: value.isoformat() + 'Z' if isinstance(value, datetime) else value for key, value in stats.items()}
    ctx = rows.c.sample_context
    measured = (ctx['monitoring_enabled'].as_boolean().is_(True) &
                or_(ctx['test_scenario'].as_string().is_(None), ctx['test_scenario'].as_string() == ''))
    peaks = db.execute(select(func.max(case((measured, rows.c.gas))),
        func.max(case((measured, rows.c.smoke))), func.max(case((measured, rows.c.temperature))))).one()
    stats.update(peak_gas_sampling=peaks[0], peak_smoke_sampling=peaks[1], peak_temperature_sampling=peaks[2])
    counts = db.execute(select(
        func.sum(case((ctx['monitoring_enabled'].as_boolean().is_(False), 1), else_=0)),
        func.sum(case((ctx['test_scenario'].as_string() != '', 1), else_=0)),
        func.sum(case((ctx['backfilled'].as_boolean().is_(True), 1), else_=0)))).one()
    events = select(Alarm).where(Alarm.device_id == device_id, Alarm.started_at < end,
                                or_(Alarm.recovered_at.is_(None), Alarm.recovered_at >= start))
    aggregate = events.subquery()
    faults = db.execute(select(aggregate.c.kind, func.count().label('count'),
        func.sum(case((aggregate.c.acknowledged_at.is_(None), 1), else_=0)).label('unacknowledged'))
        .group_by(aggregate.c.kind).order_by(func.count().desc())).mappings().all()
    details = [serialize(a) for a in db.scalars(events.order_by(Alarm.started_at.desc()).limit(40))]
    # 编写/修改日期（日志对应）：2026-10-16。恢复后的输出会随独立开阀变化，不能当作触发时执行失败。
    # 仅活动事件向模型提供当前动作比对；历史记录的原因和人工处置保留，数据库证据不被改写。
    for detail in details:
        if detail['status'] != 'active' and detail.get('response'):
            detail['response'] = {**detail['response'], 'actions': [],
                'feedback_scope': '事件已恢复；当前输出不能代表触发时执行效果，恢复开阀不等于保护失败'}
    return {'device_id': device_id, 'source': device.source, 'window_start': start.isoformat() + 'Z',
            'window_end_exclusive': end.isoformat() + 'Z', 'window_complete': end <= utcnow(),
            # 日志对应：2026-10-15。明确给出本地期间，防止模型把UTC前一日误写为北京时间日期。
            'window_start_local': start.replace(tzinfo=timezone.utc).astimezone(LOCAL).isoformat(),
            'window_end_local_exclusive': end.replace(tzinfo=timezone.utc).astimezone(LOCAL).isoformat(),
            'generated_at': utcnow().isoformat() + 'Z', 'timezone': 'Asia/Shanghai',
            'statistics': {**stats, 'standby_count': int(counts[0] or 0), 'drill_count': int(counts[1] or 0),
                           'backfill_count': int(counts[2] or 0)}, 'faults': [dict(row) for row in faults],
            'events': [{'id': a['id'], 'kind': a['kind'], 'status': a['status'], 'started_at': a['started_at'],
                        'recovered_at': a['recovered_at'], 'acknowledged': bool(a['acknowledged_at']),
                        'message': a['message'], 'test_scenario': a['evidence'].get('test_scenario', ''),
                        'response': a.get('response')} for a in details],
            'event_detail_limit': 40, 'limitations': ['量程未标定，燃气输入为电位器；引脚与脉宽输出不是机械动作测量。',
                'peak_*是包含演练的全部存档峰值；peak_*_sampling才是已标明非演练的实际采样峰值，旧未标记记录不充当实际采样。补传按采集时间归属。',
                '没有持续在线率测量和完整事故数据，不生成虚假的在线率或事故概率。']}


class ReportInput(BaseModel):
    """自然周／自然月报告请求；生成写入需要操作员权限。"""
    device_id: str
    period: Literal['weekly', 'monthly']
    anchor: date
    use_model: bool = True


@router.get('/reports/statistics')
def statistics(device_id: str, start: datetime, end: datetime,
               user=Depends(current_user), db=Depends(get_db, scope='function')):
    """只读故障与采样统计，所有账号可查询，不触发外部模型费用。"""
    first, last = utc(start), utc(end)
    if first >= last:
        raise HTTPException(422, '结束时间必须晚于开始时间')
    return report_facts(db, device_id, first, last)


@router.post('/reports', status_code=201)
def create_report(data: ReportInput, user=Depends(operator), db=Depends(get_db, scope='function')):
    """冻结统计事实，调用专家分析后保存；模型失败也明确保存统计版，不影响监测线程。"""
    start, end = period_bounds(data.period, data.anchor)
    # 日志对应：2026-10-15。MySQL的SUM返回Decimal；先标准化，JSON存储与模型输入使用同一份事实。
    facts = jsonable_encoder(report_facts(db, data.device_id, start, end))
    analysis = expert_analysis(facts, '运行周报' if data.period == 'weekly' else '运行月报', data.use_model)
    report = OperationReport(period=data.period, device_id=data.device_id, starts_at=start, ends_at=end,
                             created_by=user.username, facts=facts, analysis=analysis)
    db.add(report)
    db.flush()
    audit(db, user.username, 'report.generate', report.id, period=data.period, provider=analysis['provider'])
    return serialize(report)


@router.get('/reports')
def list_reports(device_id: str | None = None, before_id: int | None = None,
                 user=Depends(current_user), db=Depends(get_db, scope='function')):
    """按游标读取已保存报告，生成日期与统计期间分别显示。"""
    query = select(OperationReport)
    if device_id:
        query = query.where(OperationReport.device_id == device_id)
    if before_id:
        query = query.where(OperationReport.id < before_id)
    return [serialize(row) for row in db.scalars(query.order_by(OperationReport.id.desc()).limit(50))]


@router.get('/reports/{report_id}/download')
def download_report(report_id: int, user=Depends(current_user), db=Depends(get_db, scope='function')):
    """下载可阅读Markdown报告，包含统计依据、故障排名与专家建议，不需打开数据库。"""
    report = db.get(OperationReport, report_id)
    if not report:
        raise HTTPException(404, '报告不存在')
    facts, advice = report.facts, report.analysis
    local_start = report.starts_at.replace(tzinfo=timezone.utc).astimezone(LOCAL).isoformat()
    local_end = report.ends_at.replace(tzinfo=timezone.utc).astimezone(LOCAL).isoformat()
    lines = [f'# 厨房监测运行{"周报" if report.period == "weekly" else "月报"}',
             f'设备：{report.device_id}；生成：{report.created_at.isoformat()}Z',
             f'统计区间：{local_start} 至 {local_end}（右端不含，北京时间）',
             '期间尚未结束，本报告仅反映生成时已有记录。' if not facts['window_complete'] else '完整期间统计。',
             f'分析来源：{advice["provider"]}；状态：{advice["model_status"]}', '', '## 采样统计']
    metric_names = {'sample_count':'采样存档总数','standby_count':'待机心跳记录','drill_count':'演练记录','backfill_count':'离线补传记录',
        'peak_gas':'全部存档燃气峰值（含演练）','peak_smoke':'全部存档烟雾峰值（含演练）','peak_temperature':'全部存档温度峰值（含演练）',
        'peak_gas_sampling':'已标明实际采样的燃气峰值','peak_smoke_sampling':'已标明实际采样的烟雾峰值',
        'peak_temperature_sampling':'已标明实际采样的温度峰值','first_sample':'首次采集时间（UTC）','last_sample':'最近采集时间（UTC）'}
    lines += [f'- {metric_names.get(key,key)}：{value if value is not None else "无数据"}' for key, value in facts['statistics'].items()]
    lines += ['', '## 主要异常（包含演练）'] + [f'- {FAULT_NAMES.get(row["kind"],row["kind"])}：{row["count"]}项，待确认{row["unacknowledged"]}项' for row in facts['faults']]
    lines += ['', '## 运行分析', advice['summary']]
    for key, title in [('evidence', '证据'), ('hypotheses', '原因假设'), ('recommendations', '核查建议'), ('uncertainties', '不确定性')]:
        lines += ['', '## ' + title] + ['- ' + item for item in advice.get(key, [])]
    lines += ['', '## 相关事件索引（最多40条，故障统计涵盖完整期间）']
    lines += [f'- #{item["id"]} {item["kind"]}；{item["status"]}；{item["started_at"]}；{item["message"]}' for item in facts['events']]
    lines += ['', '## 数据边界'] + ['- ' + item for item in facts['limitations']]
    return Response('\n\n'.join(lines), media_type='text/markdown; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="operation-report-{report.id}.md"'})
