"""HTTP 请求和响应的数据契约。

Pydantic 模型在进入业务层之前完成长度、范围、枚举和时间校验，
业务函数因此可以专注于状态变更，不需要重复处理用户输入。
"""

from datetime import datetime, timedelta, timezone
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class LoginInput(BaseModel):
    """登录表单。"""
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class SampleInput(BaseModel):
    """设备遥测包；拒绝未知字段，避免协议拼写错误被静默忽略。"""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    boot_id: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9-]+$')
    sequence: int = Field(ge=0)
    sampled_at: datetime
    gas: float | None = Field(default=None, ge=0, le=100)
    smoke: float | None = Field(default=None, ge=0, le=100)
    temperature: float | None = Field(default=None, ge=-40, le=150)
    flame: bool = False
    valid: bool = True
    local_alarm: Literal['normal', 'gas', 'fire', 'sensor_fault', 'multiple'] = 'normal'
    actuators: dict[Literal['valve', 'fan', 'power', 'buzzer'], Literal['open', 'closed', 'on', 'off']] = Field(default_factory=dict)

    @model_validator(mode='after')
    def check_sample(self):
        # 设备时间必须带时区，避免不同设备把同一条数据写成不同时间线。
        if self.sampled_at.tzinfo is None:
            raise ValueError('sampled_at 必须包含时区')
        if self.sampled_at.astimezone(timezone.utc) > datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=30):
            raise ValueError('采样时间不能明显晚于服务器时间')
        if self.valid and any(getattr(self, k) is None for k in ('gas', 'smoke', 'temperature')):
            raise ValueError('有效采样必须包含全部测量值')
        return self


class RuleInput(BaseModel):
    """报警规则更新请求。"""
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


class CommandInput(BaseModel):
    """用户控制命令。"""
    action: Literal['close_valve', 'silence', 'self_test']
    idempotency_key: str = Field(min_length=8, max_length=80)


class CommandResult(BaseModel):
    """设备对控制命令的执行回执。"""
    success: bool
    message: str = Field(max_length=500)


class NoteInput(BaseModel):
    """报警备注或确认说明。"""
    note: str = Field(min_length=1, max_length=500)


class ScenarioInput(BaseModel):
    """模拟器场景切换请求。"""
    scenario: Literal['normal', 'gas', 'fire', 'spike', 'sensor_fault', 'offline', 'command_timeout']


class UserInput(BaseModel):
    """管理员创建用户请求。"""
    username: str = Field(pattern=r'^[a-zA-Z0-9_-]{3,32}$')
    password: str = Field(min_length=10, max_length=128)
    role: Literal['admin', 'operator', 'viewer']
