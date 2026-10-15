"""文件职责：设备帧与 TCP 转发测试。
主要功能：覆盖编码解码、占位时间、无效帧、严格回执和独立上报身份。
技术栈：pytest、asyncio、HTTPX MockTransport、本机 TCP。
模块联动：对照 gateway.protocol 和 HardwareGateway；使用构造样本，不作为 Wi-Fi 实物连通证据。
编写/修改日期（日志对应）：2026-09-25。
"""
from datetime import datetime, timezone
import asyncio

import httpx
import pytest

from backend.schemas import SampleInput
from gateway.protocol import ProtocolError, command_result_payload, decode_frame, encode_frame, telemetry_payload
from gateway.server import HardwareGateway


def telemetry():
    """构造包含完整设备帧字段的测试样本，供协议编码和 TCP 转发测试复用。
    编写/修改日期（日志对应）：2026-09-25。
    """
    return {
        "type": "telemetry", "boot_id": "stm32f103-hwtest", "sequence": 4,
        "sampled_at": "1970-01-01T00:00:00Z", "gas": 12, "smoke": 3,
        "temperature": 25.0, "flame": False, "valid": True, "local_alarm": "normal",
        "actuators": {"valve": "open", "fan": "off", "power": "off", "buzzer": "off"},
        "raw": {"gas_ao": 500},
    }


def test_frame_round_trip_and_rtc_stamp():
    """验证一帧 JSON 可往返编解码，固件占位时间由指定接收时间补齐。
    编写/修改日期（日志对应）：2026-09-25。
    """
    packet = decode_frame(encode_frame(telemetry()))
    payload = telemetry_payload(packet, datetime(2026, 10, 14, tzinfo=timezone.utc))
    assert payload["sampled_at"] == "2026-10-14T00:00:00Z"
    assert payload["raw"] == {"gas_ao": 500} and "type" not in payload


def test_command_result_is_strict():
    """验证控制回执只接受有效命令编号、布尔成功状态和长度受限的说明。
    编写/修改日期（日志对应）：2026-09-25。
    """
    command_id, payload = command_result_payload({"type": "command_result", "command_id": "cmd-1",
                                                   "success": True, "message": "done"})
    assert command_id == "cmd-1"
    assert payload == {"success": True, "message": "done"}


def test_invalid_or_oversized_frame_is_rejected():
    """验证非法 JSON、未知帧和超长数据在进入业务接口之前被拒绝。
    编写/修改日期（日志对应）：2026-09-25。
    """
    with pytest.raises(ProtocolError):
        decode_frame(b"not-json\n")
    with pytest.raises(ProtocolError):
        encode_frame({"type": "telemetry", "data": "x" * 5000})


def test_gateway_forwards_strict_sample_with_auth_and_session_boot_id():
    """通过本机 TCP 与模拟 HTTP 接口验证遥测转换、独立设备认证和连接启动身份。
    编写/修改日期（日志对应）：2026-09-25。
    """
    seen = []

    def api(request):
        """接收 HTTPX 模拟请求，保留认证与载荷供测试断言，并返回构造的遥测接收结果。
        编写/修改日期（日志对应）：2026-09-25。
        """
        seen.append(request)
        return httpx.Response(200, json={"accepted": True})

    async def run():
        """在本机建立临时 TCP 网关连接，发送测试帧并核对返回结果，结束后释放服务与客户端。
        编写/修改日期（日志对应）：2026-09-25。
        """
        gateway = HardwareGateway("http://127.0.0.1:8000", "kitchen-001", "local-test-token")
        await gateway.http.aclose()
        gateway.http = httpx.AsyncClient(transport=httpx.MockTransport(api))
        try:
            result = await gateway.post_telemetry(telemetry())
        finally:
            await gateway.close()
        return result

    assert asyncio.run(run()) == {"accepted": True}
    assert seen[0].url.path == "/api/v1/ingest/devices/kitchen-001/telemetry"
    assert seen[0].headers["authorization"] == "Bearer local-test-token"
    sample = SampleInput.model_validate_json(seen[0].content)
    assert sample.boot_id.startswith("gateway-")
    assert sample.sequence == 4
