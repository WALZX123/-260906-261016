"""文件职责：无线网关认证和双向命令协议回归。
主要功能：使用隔离帧流验证握手、规则下发、真实回执关联和未认证连接拒绝。
技术栈：pytest、asyncio、HTTPX MockTransport；模块联动：gateway.server 与设备 API。
编写/修改日期（日志对应）：2026-10-12、2026-10-15。
"""
import asyncio
import json
import zlib
from pathlib import Path
import httpx
from gateway import server


class Writer:
    """记录网关实际输出的字节与关闭状态，不运行真实硬件。"""
    def __init__(self):
        self.data = bytearray()
        self.closed = False

    def get_extra_info(self, name):
        """提供固定的隔离客户端地址。"""
        return ('192.168.43.22', 12345)

    def write(self, data):
        """保存向设备发出的内容，供外部协议断言。"""
        self.data.extend(data)

    async def drain(self):
        """模拟已完成网络发送。"""

    def close(self):
        """记录连接关闭，不影响其他客户端对象。"""
        self.closed = True

    async def wait_closed(self):
        """模拟正常结束连接。"""


def frame(data):
    """构造带换行的真实协议输入。"""
    return json.dumps(data).encode() + b'\n'


def test_authenticated_wifi_command_and_receipt(tmp_path, monkeypatch):
    """握手通过才转发遥测；没有 MCU 回执时只下发命令，匹配回执后才报告成功。"""
    monkeypatch.setattr(server, 'PROJECT_ROOT', tmp_path)
    runtime = tmp_path / '.runtime'
    runtime.mkdir()
    (runtime / 'wifi.json').write_text(json.dumps({'token': 'test-secret'}))
    command_id = 'hardware-command-only-for-test'
    sequence = zlib.crc32(command_id.encode()) or 1
    receipts = []

    def request(req):
        """模拟设备 API，记录网关报告的执行结果，不把接收命令当作成功。"""
        if req.url.path.endswith('/control'):
            return httpx.Response(200, json={'rules_revision': 9, 'rules': {
                'gas_threshold': 60, 'smoke_threshold': 45, 'temperature_threshold': 60},
                'commands': [{'id': command_id, 'action': 'inject_smoke'}]})
        if req.url.path.endswith('/result'):
            receipts.append(json.loads(req.content))
        return httpx.Response(200, json={'accepted': True})

    async def run():
        """用两帧遥测分别表示执行前和执行后，检查整个串行处理链。"""
        gateway = server.HardwareGateway('http://localhost', 'real', 'device-secret')
        await gateway.http.aclose()
        gateway.http = httpx.AsyncClient(transport=httpx.MockTransport(request))
        reader = asyncio.StreamReader()
        reader.feed_data(frame({'type': 'hello', 'token': 'test-secret'}))
        packet = {'type': 'telemetry', 'boot_id': 'mcu', 'sequence': 1, 'sampled_at': '1970-01-01T00:00:00Z',
                  'gas': 10, 'smoke': 5, 'temperature': 25, 'diagnostics': {}}
        reader.feed_data(frame(packet))
        packet.update(sequence=2, diagnostics={'command_sequence': sequence, 'command_result': 1})
        reader.feed_data(frame(packet))
        reader.feed_eof()
        writer = Writer()
        await gateway.handle_client(reader, writer)
        await gateway.close()
        assert writer.closed
        assert ('C,%d,12\n' % sequence).encode() in writer.data
        assert b'R,9,60,45,6000\n' in writer.data
        assert len(receipts) == 1 and receipts[0]['success'] is True
        assert not (runtime / 'wifi_link.json').exists()

    asyncio.run(run())


def test_unknown_wifi_client_cannot_replace_existing_link(tmp_path, monkeypatch):
    """错误密钥不能中断已有连接，也不能取得设备 API 令牌。"""
    monkeypatch.setattr(server, 'PROJECT_ROOT', tmp_path)
    (tmp_path / '.runtime').mkdir()
    (tmp_path / '.runtime/wifi.json').write_text(json.dumps({'token': 'correct-secret'}))

    async def run():
        """在未认证客户端到达前预置有效连接，验证只关闭错误客户端。"""
        gateway = server.HardwareGateway('http://localhost', 'real', 'device-secret')
        existing = Writer()
        gateway.writer = existing
        reader = asyncio.StreamReader()
        reader.feed_data(frame({'type': 'hello', 'token': 'wrong-secret'}))
        reader.feed_eof()
        visitor = Writer()
        await gateway.handle_client(reader, visitor)
        assert visitor.closed and not existing.closed and gateway.writer is existing
        await gateway.close()

    asyncio.run(run())
