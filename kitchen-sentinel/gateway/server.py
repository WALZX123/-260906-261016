"""文件职责：MB026 TCP 透传接入服务。
主要功能：管理单设备连接，转发遥测与回执，认证连接、下发规则和命令并保存 MCU 回执。
技术栈：asyncio TCP Stream、HTTPX 异步客户端、UUID。
模块联动：protocol 校验帧，再调用设备 API；向 STM32 下发远程命令，SWD 租约避免两个通道重复控制。
编写/修改日期（日志对应）：2026-09-30、2026-10-02、2026-10-15。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import json
import secrets
import time
import zlib
from math import ceil
from typing import Any
from uuid import uuid4

import httpx
from backend.core.config import settings, PROJECT_ROOT
from gateway.swd_control import ACTIONS, RESULTS

from gateway.protocol import (
    ProtocolError,
    command_result_payload,
    decode_frame,
    telemetry_payload,
)

LOG = logging.getLogger("kitchen.gateway")


class HardwareGateway:
    """使用独立硬件身份和随机握手密钥转发遥测、阈值、命令及真实固件回执。
    编写/修改日期（日志对应）：2026-09-30。
    """
    def __init__(self, api_base_url: str, device_id: str, device_token: str):
        """保存后端地址和独立硬件身份，创建不使用系统代理的异步 HTTP 客户端及本次连接启动编号。
        编写/修改日期（日志对应）：2026-09-30。
        """
        self.api_base_url = api_base_url.rstrip("/")
        self.device_id = device_id
        self.device_token = device_token
        self.http = httpx.AsyncClient(timeout=5.0, trust_env=False)
        self.writer: asyncio.StreamWriter | None = None
        self.session_boot_id = "gateway-" + uuid4().hex

    @property
    def headers(self) -> dict[str, str]:
        """按当前硬件令牌构造 Bearer 请求头，只用于网关到设备 API 的认证，不输出令牌。
        编写/修改日期（日志对应）：2026-09-30。
        """
        return {"Authorization": f"Bearer {self.device_token}"}

    def endpoint(self, suffix: str) -> str:
        """将设备编号和接口后缀拼成设备接入 URL，保证遥测与回执使用同一硬件身份。
        编写/修改日期（日志对应）：2026-09-30。
        """
        return f"{self.api_base_url}/api/v1/ingest/devices/{self.device_id}/{suffix}"

    async def close(self) -> None:
        """关闭异步 HTTP 客户端并释放连接池，由 TCP 服务退出分支调用。
        编写/修改日期（日志对应）：2026-09-30。
        """
        await self.http.aclose()

    async def post_telemetry(self, packet: dict[str, Any]) -> dict[str, Any]:
        """校验遥测结构，补连接启动身份及 TCP 来源，再向设备遥测接口提交并返回接收结果。
        编写/修改日期（日志对应）：2026-09-30。
        """
        payload = telemetry_payload(packet)
        # 固件暂无 RTC 或持久启动计数，用当前连接身份避免不同重启的序号互相覆盖。
        payload["boot_id"] = self.session_boot_id
        payload["transport"] = "tcp"
        response = await self.http.post(self.endpoint("telemetry"), json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()

    async def post_command_result(self, packet: dict[str, Any]) -> dict[str, Any]:
        """严格解析设备回执后提交对应命令的结果接口，返回后端保存状态。
        编写/修改日期（日志对应）：2026-09-30。
        """
        command_id, payload = command_result_payload(packet)
        response = await self.http.post(
            self.endpoint(f"commands/{command_id}/result"), json=payload, headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """管理当前 TCP 客户端，逐行校验帧并转发 API，回复接收或错误结果，最终关闭连接。
        编写/修改日期（日志对应）：2026-09-30。
        """
        peer = writer.get_extra_info("peername")
        lease = PROJECT_ROOT / '.runtime/wifi_link.json'
        try:
            # 日志对应：2026-10-15。先验证本机配置的随机密钥，未认证连接不能替换有效设备。
            hello = json.loads(await asyncio.wait_for(reader.readline(), timeout=6))
            config = json.loads((PROJECT_ROOT / '.runtime/wifi.json').read_text(encoding='utf-8'))
            if hello.get('type') != 'hello' or not secrets.compare_digest(str(hello.get('token', '')), config['token']):
                raise ProtocolError('wireless authentication rejected')
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
            self.writer = writer
            self.session_boot_id = 'wifi-' + uuid4().hex
            LOG.info('authenticated Wi-Fi device connected: %s', peer)
            writer.write(b'K\n')
            await writer.drain()
            last_sequence = -1
            last_sent = 0
            while line := await asyncio.wait_for(reader.readline(), timeout=6):
                packet = decode_frame(line)
                if packet['type'] != 'telemetry':
                    await self.post_command_result(packet)
                    continue
                if packet.get('sequence', 0) < last_sequence:
                    self.session_boot_id = 'wifi-' + uuid4().hex
                last_sequence = packet.get('sequence', 0)
                if packet.get('monitoring_enabled') is False:
                    packet.update(gas=None, smoke=None, temperature=None, flame=False, raw=None, filtered=None,
                                  local_alarm='normal')
                await self.post_telemetry(packet)
                # 租约只在认证且 API 接收真实遥测后续期；SWD 见租约让出控制，断网后自动接管。
                lease.write_text(json.dumps({'at': time.time(), 'peer': peer[0]}), encoding='utf-8')
                control = await self.http.get(self.endpoint('control'), headers=self.headers)
                control.raise_for_status()
                data = control.json()
                rules = data['rules']
                output = 'K\nR,%d,%d,%d,%d\n' % (data['rules_revision'], ceil(rules['gas_threshold']),
                        ceil(rules['smoke_threshold']), round(rules['temperature_threshold'] * 100))
                if data.get('commands'):
                    command = data['commands'][0]
                    sequence = zlib.crc32(command['id'].encode('ascii')) or 1
                    diagnostics = packet.get('diagnostics') or {}
                    if diagnostics.get('command_sequence') == sequence:
                        result = diagnostics.get('command_result', 0)
                        receipt = await self.http.post(self.endpoint('commands/' + command['id'] + '/result'),
                            headers=self.headers, json={'success': result == 1,
                            'message': RESULTS.get(result, '未知固件回执') + '（Wi-Fi 双向通道）'})
                        if receipt.status_code != 409:
                            receipt.raise_for_status()
                    else:
                        output += 'C,%d,%d\n' % (sequence, ACTIONS[command['action']])
                        if last_sent != sequence:
                            LOG.info('Wi-Fi command sent: action=%s sequence=%s', command['action'], sequence)
                            last_sent = sequence
                writer.write(output.encode('ascii'))
                await writer.drain()
        except (OSError, ValueError, TimeoutError, ProtocolError, httpx.HTTPError) as exc:
            LOG.warning('Wi-Fi link ended: %s', type(exc).__name__)
        finally:
            if self.writer is writer:
                self.writer = None
                lease.unlink(missing_ok=True)
            writer.close()
            await writer.wait_closed()
            LOG.info("device link closed: %s", peer)


async def run(args: argparse.Namespace) -> None:
    """建立硬件网关和 TCP 监听，交由 asyncio 持续服务；退出时始终释放 HTTP 连接。
    编写/修改日期（日志对应）：2026-09-30。
    """
    gateway = HardwareGateway(args.api_base_url, args.device_id, args.device_token)
    server = await asyncio.start_server(gateway.handle_client, args.listen_host, args.listen_port,
                                        limit=4096)
    addresses = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    LOG.info("hardware gateway listening on %s", addresses)
    try:
        async with server:
            await server.serve_forever()
    finally:
        await gateway.close()


def main() -> None:
    """读取监听地址和硬件令牌参数，验证身份配置后启动异步 TCP 服务。
    编写/修改日期（日志对应）：2026-09-30。
    """
    parser = argparse.ArgumentParser(description="Kitchen Sentinel STM32 TCP gateway")
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=9000)
    parser.add_argument("--api-base-url", default=os.getenv("KITCHEN_API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--device-id", default=os.getenv("KITCHEN_DEVICE_ID", "stm32-001"))
    parser.add_argument("--device-token", default=settings().hardware_device_token)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not args.device_token:
        parser.error("Run python -m scripts.register_hardware first, or supply a hardware device token")
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

