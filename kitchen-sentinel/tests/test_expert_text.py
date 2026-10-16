"""文件职责：辅助分析中文正文整理回归。
功能：验证已知术语翻译、时间换算、证据数值保留及元数据不被改写。
技术栈：pytest、纯文本函数；关联expert接口和报告下载，不调用外部模型。
编写/修改日期（日志对应）：2026-10-16。
"""
from backend.services.expert_text import chinese_advice, chinese_text


def test_chinese_terms_preserve_evidence_and_timezone():
    """将协议术语转成人话，但保留事件号、指标和未知硬件型号，不混淆日期。"""
    text = chinese_text('事件#105在2026-10-15T23:58:00Z出现`supply_low`，ADC为123，GPIO/PWM仅为control_outputs，型号F103C8保留。')
    assert '2026年10月16日 07:58:00（北京时间）' in text
    assert '供气演示低值异常' in text and '引脚输出/脉宽控制' in text
    assert '#105' in text and '123' in text and 'F103C8' in text
    assert '`' not in text and 'control_outputs' not in text


def test_only_user_facing_values_are_translated():
    """审计用模型名和状态不变，结论及建议以中文呈现，接口键保持兼容。"""
    result = chinese_advice({'summary': 'MCU报告supply_low', 'evidence': ['cache_pending=15'],
                             'provider': 'DeepSeek', 'model_status': 'succeeded'})
    assert result['provider'] == 'DeepSeek' and result['model_status'] == 'succeeded'
    assert result['summary'] == '单片机报告供气演示低值异常'
    assert result['evidence'] == ['待补传样本数=15']


def test_report_excludes_recovered_current_outputs_without_rewriting_evidence():
    """恢复后人工开阀的当前比对不能当作历史保护失败，数据库原始证据仍保留。"""
    from datetime import timedelta
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.core.db import Base
    from backend.models import Device, Alarm, utcnow
    from backend.api.archive import report_facts
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Device(id='text-test', name='报告边界测试', location='test', source='hardware', token_hash='unused'))
        db.flush()
        actions = [{'actuator': 'valve', 'expected': 'closed', 'reported': 'open', 'matched': False}]
        alarm = Alarm(device_id='text-test', kind='supply_low', severity='warning', status='recovered',
                      started_at=utcnow()-timedelta(minutes=2), recovered_at=utcnow()-timedelta(minutes=1),
                      message='演示事件已恢复', timeline=[], evidence={'response': {'actions': actions, 'manual_required': True}})
        db.add(alarm)
        db.flush()
        facts = report_facts(db, 'text-test', utcnow()-timedelta(days=1), utcnow()+timedelta(days=1))
        assert facts['events'][0]['response']['actions'] == []
        assert '不能代表' in facts['events'][0]['response']['feedback_scope']
        assert alarm.evidence['response']['actions'] == actions
    engine.dispose()
