"""文件职责：将本机私有无线配置安全提交到 MCU RAM。
主要功能：固定偏移、有界字符串和版本最后提交；技术栈：Python、pyOCD、JSON。
模块联动：backend.api.wifi、kitchen_wifi.h；不记录热点密码。编写/修改日期（日志对应）：2026-10-15。
"""
import json
from backend.core.config import PROJECT_ROOT


def apply_wifi(target, address):
    """读取私有配置，仅在修订不同且 RAM 签名匹配时提交；MCU 重启后自动重新配置网络。"""
    path = PROJECT_ROOT / '.runtime/wifi.json'
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding='utf-8'))
    magic, revision = target.read_memory_block32(address, 2)
    if magic != 0x4649534B:
        raise RuntimeError('Wi-Fi config ABI mismatch')
    if revision == data['revision']:
        return
    offset = 16
    for name, size in [('ssid', 33), ('password', 65), ('host', 16), ('token', 65)]:
        raw = data[name].encode('utf-8')
        if len(raw) >= size:
            raise ValueError('Wi-Fi configuration field too long: ' + name)
        target.write_memory_block8(address + offset, list(raw.ljust(size, b'\0')))
        offset += size
    target.write32(address + 4, data['revision'])
    target.flush()
