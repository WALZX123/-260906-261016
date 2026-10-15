"""文件职责：设备和页面请求的数据契约。
主要功能：校验采样原始值、时间、数据质量、动作、规则、人员备注和账号字段。
技术栈：Pydantic 2、Field、Literal、model_validator。
模块联动：设备网关、模拟器和 React 经 API 使用这些模型；校验通过后才进入 monitoring，采集有效与标定状态分开。
编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-09-21；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
"""

from datetime import datetime, timedelta, timezone
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class LoginInput(BaseModel):
    """登录表单。
    编写/修改日期（日志对应）：2026-09-21。
    """
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RawChannels(BaseModel):
    """日志对应：2026-09-21。统一 STM32 ADC 和数字输入结构，保留未标定的原始量程。
    """
    model_config = ConfigDict(extra='forbid')
    smoke_ao: int | None = Field(default=None, ge=0, le=4095)
    temp_ao: int | None = Field(default=None, ge=0, le=4095)
    gas_ao: int | None = Field(default=None, ge=0, le=4095)
    flame_ao: int | None = Field(default=None, ge=0, le=4095)
    smoke_do: int | None = Field(default=None, ge=0, le=1)
    flame_do: int | None = Field(default=None, ge=0, le=1)


class SampleInput(BaseModel):
    """设备遥测包；拒绝未知字段，避免协议拼写错误被静默忽略。
    编写/修改日期（日志对应）：2026-09-21。
    """
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    boot_id: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9-]+$')
    sequence: int = Field(ge=0)
    sampled_at: datetime
    gas: float | None = Field(default=None, ge=0, le=100)
    smoke: float | None = Field(default=None, ge=0, le=100)
    temperature: float | None = Field(default=None, ge=-40, le=150)
    flame: bool = False
    valid: bool = True
    io_valid: bool | None = None
    local_alarm: Literal['normal', 'gas', 'fire', 'sensor_fault', 'multiple'] = 'normal'
    actuators: dict[Literal['valve', 'fan', 'power', 'buzzer'], Literal['open', 'closed', 'on', 'off']] = Field(default_factory=dict)
    # 日志对应：2026-09-30 数据上报。传输方式与原始通道单独保存，不伪装成浓度或温度。
    raw: RawChannels | None = None
    # 日志对应：2026-09-22。滤波结果与原始量分开，便于确认噪声变化和窗口启动过程。
    filtered: RawChannels | None = None
    # 日志对应：2026-09-26。缺少硬件保护而隔离的通道必须明确报告为未接入。
    disabled_sensors: list[Literal['smoke']] = Field(default_factory=list)
    # 日志对应：2026-09-30。使用实机报告的版本，避免把尚未下载的源码版本写到设备信息中。
    firmware: str | None = Field(default=None, min_length=1, max_length=64)
    transport: Literal['swd', 'uart', 'tcp', 'simulator'] | None = None
    # 日志对应：2026-10-02。执行能力由实际固件上报，旧固件不能仅靠网页按钮获得控制能力。
    control_capabilities: list[Literal['close_valve', 'silence', 'self_test', 'test_buzzer', 'test_fan', 'test_relay', 'test_servo', 'start_monitoring', 'stop_monitoring', 'open_valve', 'inject_gas', 'inject_smoke', 'inject_temperature', 'inject_flame', 'inject_multiple', 'cancel_injection']] = Field(default_factory=list)
    # 日志对应：2026-10-15。待机心跳与真实采样分开，演练标记随数据留档，禁止伪装现场测量。
    monitoring_enabled: bool = True
    test_scenario: str = Field(default='', max_length=32)
    diagnostics: dict[str, int] = Field(default_factory=dict, max_length=24)

    @model_validator(mode='after')
    def check_sample(self):
        # 设备时间必须带时区，避免不同设备把同一条数据写成不同时间线。
        """校验采样时间带时区且不过度超前；有效采样须包含完整数值。返回当前 Pydantic 对象交给设备入库接口。
        编写/修改日期（日志对应）：2026-09-21。
        """
        if self.sampled_at.tzinfo is None:
            raise ValueError('sampled_at 必须包含时区')
        if self.sampled_at.astimezone(timezone.utc) > datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=30):
            raise ValueError('采样时间不能明显晚于服务器时间')
        if self.valid and any(getattr(self, k) is None for k in ('gas', 'smoke', 'temperature')):
            raise ValueError('有效采样必须包含全部测量值')
        return self


class RuleInput(BaseModel):
    """报警规则更新请求。
    编写/修改日期（日志对应）：2026-09-21。
    """
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    revision: int
    gas_threshold: float = Field(ge=10, le=95)
    smoke_threshold: float = Field(ge=10, le=95)
    temperature_threshold: float = Field(ge=35, le=120)
    hold_seconds: float = Field(ge=0, le=30)
    recovery_seconds: float = Field(ge=1, le=60)
    hysteresis: float = Field(ge=1, le=9)
    offline_seconds: int = Field(ge=6, le=120)
    command_timeout_seconds: int = Field(ge=5, le=120)
    # 日志对应：2026-10-03。自动响应范围和等待效果的上限，达到后升级人工处置。
    gas_manual_threshold: float = Field(default=80, ge=10, le=100)
    auto_response_timeout_seconds: int = Field(default=30, ge=5, le=300)

    @model_validator(mode='after')
    def check_automatic_range(self):
        """检查人工介入阈值高于自动报警触发值，避免规则范围重叠；成功返回本规则对象。
        编写/修改日期（日志对应）：2026-09-21。
        """
        if self.gas_manual_threshold <= self.gas_threshold:
            raise ValueError('人工介入阈值必须高于燃气触发阈值')
        return self


class CommandInput(BaseModel):
    """用户控制命令。
    编写/修改日期（日志对应）：2026-09-21。
    """
    action: Literal['close_valve', 'silence', 'self_test', 'test_buzzer', 'test_fan', 'test_relay', 'test_servo', 'start_monitoring', 'stop_monitoring', 'open_valve', 'inject_gas', 'inject_smoke', 'inject_temperature', 'inject_flame', 'inject_multiple', 'cancel_injection']
    idempotency_key: str = Field(min_length=8, max_length=80)


class CommandResult(BaseModel):
    """设备对控制命令的执行回执。
    编写/修改日期（日志对应）：2026-09-21。
    """
    success: bool
    message: str = Field(max_length=500)


class NoteInput(BaseModel):
    """报警备注或确认说明。
    编写/修改日期（日志对应）：2026-09-21。
    """
    note: str = Field(min_length=1, max_length=500)


class ScenarioInput(BaseModel):
    """模拟器场景切换请求。
    编写/修改日期（日志对应）：2026-09-21。
    """
    scenario: Literal['normal', 'gas', 'fire', 'spike', 'sensor_fault', 'offline', 'command_timeout']


class UserInput(BaseModel):
    """管理员创建用户请求。
    编写/修改日期（日志对应）：2026-09-21。
    """
    username: str = Field(pattern=r'^[a-zA-Z0-9_-]{3,32}$')
    password: str = Field(min_length=10, max_length=128)
    role: Literal['admin', 'operator', 'viewer']
