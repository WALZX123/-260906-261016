"""文件职责：SWD 命令提交与 MCU 回执关联。
主要功能：校验信箱签名，按提交序号发送命令，等待真实固件回执并重试上报结果。
技术栈：Python、CRC32、pyOCD 内存访问、HTTPX、单调时钟。
模块联动：gateway.swd 持有唯一探针会话，backend 设备接口提供命令，hardware_control.h 定义信箱；不通过寄存器伪造机械反馈。
编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-10-02、2026-10-09。
"""
import time
import zlib
from math import ceil

ACTIONS = {'close_valve': 1, 'silence': 2, 'self_test': 3, 'test_buzzer': 4,
           'test_fan': 5, 'test_relay': 6, 'test_servo': 7,
           'start_monitoring': 8, 'stop_monitoring': 9, 'open_valve': 10,
           'inject_gas': 11, 'inject_smoke': 12, 'inject_temperature': 13,
           'inject_flame': 14, 'inject_multiple': 15, 'cancel_injection': 16}
RESULTS = {1: '固件已执行；反馈为控制输出，实际动作请现场核对',
           2: '当前存在真实险情、设备未启用或采样尚未稳定；操作被拒绝，保护继续',
           3: '固件不支持此命令', 4: '固件算法自检或 ADC 错误检查未通过'}


class SwdCommands:
    """串行处理一个信箱命令，结果上报失败可重试，不能因重试反复操作执行器。
    编写/修改日期（日志对应）：2026-10-02。
    """

    def __init__(self, target, address, http, endpoint, token):
        """保存探针、信箱地址和已认证 HTTP 通道，初始化待完成状态。
        编写/修改日期（日志对应）：2026-10-02。
        """
        self.target, self.address, self.http = target, address, http
        self.endpoint, self.headers = endpoint, {'Authorization': f'Bearer {token}'}
        self.pending = None

    def step(self):
        """每轮先上报回执，再取下一命令；命令最长等待六秒，不阻塞 MCU 的独立保护循环。
        编写/修改日期（日志对应）：2026-10-02。
        """
        if self.pending:
            command, sequence, started = self.pending
            mailbox = self.target.read_memory_block32(self.address, 6)
            if mailbox[0:2] != [0x4348534B, 2]:
                raise RuntimeError('Command mailbox ABI mismatch')
            if mailbox[4] != sequence and time.monotonic() - started < 6:
                return
            success = mailbox[4] == sequence and mailbox[5] == 1
            message = RESULTS.get(mailbox[5], '未收到 MCU 执行回执') if mailbox[4] == sequence else 'MCU 六秒内未确认命令'
            response = self.http.post(self.endpoint + '/commands/' + command['id'] + '/result',
                                      headers=self.headers, json={'success': success, 'message': message})
            if response.status_code != 409:
                response.raise_for_status()
            self.pending = None
            return
        response = self.http.get(self.endpoint + '/control', headers=self.headers)
        response.raise_for_status()
        control = response.json()
        # 阈值数据先写、修订号最后写，固件按版本二次校验；规则同步不占用命令回执字段。
        mailbox = self.target.read_memory_block32(self.address, 12)
        if mailbox[0:2] != [0x4348534B, 2]:
            raise RuntimeError('Command mailbox ABI mismatch')
        revision = control.get('rules_revision', 0)
        if revision and mailbox[10] != revision:
            rules = control['rules']
            # MCU 的相对指标为整数，向上取整与“整数指标达到浮点阈值”语义一致。
            self.target.write32(self.address + 28, ceil(rules['gas_threshold']))
            self.target.write32(self.address + 32, ceil(rules['smoke_threshold']))
            self.target.write32(self.address + 36, round(rules['temperature_threshold'] * 100))
            self.target.write32(self.address + 24, revision)
            self.target.flush()
        commands = control.get('commands', [])
        if not commands:
            return
        command = commands[0]
        action = ACTIONS.get(command['action'])
        if not action:
            raise RuntimeError('Unsupported command action')
        mailbox = self.target.read_memory_block32(self.address, 6)
        if mailbox[0:2] != [0x4348534B, 2]:
            raise RuntimeError('Command mailbox ABI mismatch')
        sequence = zlib.crc32(command['id'].encode('ascii')) or 1
        if mailbox[4] != sequence:
            # 最后提交序号，固件只对不同于已确认序号的命令执行一次。
            self.target.write32(self.address + 12, action)
            self.target.write32(self.address + 8, sequence)
            self.target.flush()
        self.pending = (command, sequence, time.monotonic())
