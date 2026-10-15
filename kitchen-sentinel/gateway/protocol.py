"""文件职责：STM32 与电脑之间的帧协议。
主要功能：编解码换行分隔 JSON，限制帧长度，解析遥测与控制回执并补接收时间。
技术栈：Python json、UTF-8、datetime、类型校验。
模块联动：gateway.server 使用本文件转换设备帧，backend.schemas 再校验范围；补时间不代表设备 RTC 已同步。
编写/修改日期（日志对应）：2026-09-30。
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

MAX_FRAME_BYTES = 4096
TELEMETRY_TYPE = "telemetry"
COMMAND_RESULT_TYPE = "command_result"


class ProtocolError(ValueError):
    """设备帧格式或长度不满足协议时抛出的异常，供 TCP 网关统一记录并回复错误。
    编写/修改日期（日志对应）：2026-09-30。
    """


def encode_frame(packet: dict[str, Any]) -> bytes:
    """将字典编码为 UTF-8 紧凑 JSON，并追加 CRLF；超出帧长度上限抛出 ProtocolError，返回可写入 TCP 的字节串。
    编写/修改日期（日志对应）：2026-09-30。
    """
    if not isinstance(packet, dict):
        raise ProtocolError("frame must be a JSON object")
    data = (json.dumps(packet, ensure_ascii=False, separators=(",", ":")) + "\r\n").encode("utf-8")
    if len(data) > MAX_FRAME_BYTES:
        raise ProtocolError("frame exceeds 4096 bytes")
    return data


def decode_frame(line: bytes | str) -> dict[str, Any]:
    """把一行设备字节或文本解析为字典，校验编码、长度和帧类型；无效输入抛出 ProtocolError。
    编写/修改日期（日志对应）：2026-09-30。
    """
    if isinstance(line, bytes):
        if len(line) > MAX_FRAME_BYTES:
            raise ProtocolError("frame exceeds 4096 bytes")
        try:
            line = line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("frame is not UTF-8") from exc
    if len(line.encode("utf-8")) > MAX_FRAME_BYTES:
        raise ProtocolError("frame exceeds 4096 bytes")
    try:
        packet = json.loads(line.strip())
    except json.JSONDecodeError as exc:
        raise ProtocolError("frame is not valid JSON") from exc
    if not isinstance(packet, dict):
        raise ProtocolError("frame must be a JSON object")
    if packet.get("type") not in {TELEMETRY_TYPE, COMMAND_RESULT_TYPE}:
        raise ProtocolError("unsupported frame type")
    return packet


def telemetry_payload(packet: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """日志对应：2026-09-21 统一数据结构；2026-09-30 数据上报。
    
    移除帧类型并保留原始通道，由接口模型校验范围。无 RTC 固件使用 Unix 起点
    作为占位时间，网关将其替换为接收时间，不能据此声称已同步硬件时钟。
    """
    if packet.get("type") != TELEMETRY_TYPE:
        raise ProtocolError("expected telemetry frame")
    payload = {key: value for key, value in packet.items() if key != "type"}
    required = {"boot_id", "sequence", "sampled_at", "gas", "smoke", "temperature"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ProtocolError("telemetry missing: " + ", ".join(missing))
    sampled_at = str(payload["sampled_at"])
    if sampled_at.startswith("1970-01-01T00:00:00"):
        timestamp = now or datetime.now(timezone.utc)
        payload["sampled_at"] = timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return payload


def command_result_payload(packet: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """从严格回执中取命令编号和成功状态，限制说明长度；返回设备 API 需要的编号与结果字典。
    编写/修改日期（日志对应）：2026-09-30。
    """
    if packet.get("type") != COMMAND_RESULT_TYPE:
        raise ProtocolError("expected command result frame")
    command_id = packet.get("command_id")
    success = packet.get("success")
    if not isinstance(command_id, str) or not command_id:
        raise ProtocolError("command_id is required")
    if not isinstance(success, bool):
        raise ProtocolError("success must be boolean")
    message = packet.get("message", "")
    if not isinstance(message, str) or len(message) > 500:
        raise ProtocolError("message must be a short string")
    return command_id, {"success": success, "message": message}
