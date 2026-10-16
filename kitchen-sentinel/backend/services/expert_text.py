"""文件职责：辅助分析正文的中文术语整理。
功能：将已知内部字段、状态与缩写转成中文，统一带时区的事件时间；不改变数值、事件编号或未知词。
技术栈：Python正则、datetime、zoneinfo；关联expert结构化分析和报告下载。
编写/修改日期（日志对应）：2026-10-16。元数据和接口字段保持原协议，只整理面向人的正文。
"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

TERMS = {
    'supply_low': '供气演示低值异常', 'supply_low_latched': '供气异常锁存',
    'supply_demo_enabled': '供气演示开关', 'supply_state': '供气评估状态',
    'test_scenario': '演练场景', 'monitoring_enabled': '采样启用状态',
    'local_alarm': '本地报警', 'gas_threshold': '燃气高值阈值',
    'supply_low_threshold': '供气低值阈值', 'gas_manual_threshold': '燃气升级人工阈值',
    'adc_error_count': '采样错误次数', 'processing_test_failures': '算法自检失败项',
    'cache_pending': '待补传样本数', 'cache_dropped': '存档缺口计数',
    'clock_quality': '设备时间质量', 'device_synced': '设备已校时',
    'control_outputs': '控制输出报告', 'signal_recovered': '信号已恢复',
    'manual_required': '需要人工处理', 'acknowledged_at': '人工确认时间',
    'sample_count': '采样记录数', 'backfill_count': '离线补传记录数',
    'window_start_local': '统计开始时间', 'window_end_local_exclusive': '统计结束时间且不含该时刻',
    'sensor_fault': '采样故障', 'control_fault': '控制执行异常', 'storage_fault': '采样存档缺口',
    'command_timeout': '控制命令超时', 'multiple': '复合险情', 'flame': '火焰',
    'smoke': '烟雾', 'temperature': '温度', 'gas': '燃气', 'offline': '设备离线',
    'backfilled': '离线补传', 'backfill': '离线补传', 'standby': '待机',
    'recovered': '信号已恢复', 'active': '触发中', 'normal': '正常',
    'true': '是', 'false': '否', 'null': '未提供',
    'MCU': '单片机', 'STM32': '单片机', 'ADC': '模数采集', 'NTC': '热敏电阻',
    'GPIO': '引脚输出', 'PWM': '脉宽控制', 'WiFi': '无线网络', 'Wi-Fi': '无线网络',
    'API': '服务接口', 'DeepSeek': '模型服务', 'JSON': '结构化数据',
    'UTC': '协调世界时', 'TCP': '网络连接', 'SWD': '调试通道',
}
PATTERN = re.compile(r'(?<![A-Za-z0-9_])(' + '|'.join(re.escape(k) for k in sorted(TERMS, key=len, reverse=True)) + r')(?![A-Za-z0-9_])')
TIMESTAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})')


def chinese_text(value: str) -> str:
    """只替换完整已知术语，避免改写硬件型号、数值或单词的一部分；无效日期原样保留。"""
    def local_time(match):
        """将明确带时区的时间换算成北京时间，避免直接删除时区导致日期误解。"""
        try:
            return datetime.fromisoformat(match.group().replace('Z', '+00:00')).astimezone(
                ZoneInfo('Asia/Shanghai')).strftime('%Y年%m月%d日 %H:%M:%S（北京时间）')
        except ValueError:
            return match.group()
    result = TIMESTAMP.sub(local_time, value)
    result = PATTERN.sub(lambda m: TERMS[m.group()], result)
    # 模型偶尔给已知字段加代码符号，整理为普通文字；不移除内容和事实依据。
    return result.replace('`', '')


def chinese_advice(content: dict) -> dict:
    """只处理面向用户的五类文本，保留模型标识、状态及协议键供审计。"""
    return {key: chinese_text(value) if key == 'summary' else
            [chinese_text(item) for item in value] if key in ('evidence', 'hypotheses', 'recommendations', 'uncertainties') else value
            for key, value in content.items()}
