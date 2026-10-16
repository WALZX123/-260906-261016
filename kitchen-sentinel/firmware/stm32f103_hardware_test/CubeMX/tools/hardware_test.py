"""文件职责：STM32 下载、状态与舵机配置诊断工具。
主要功能：确认芯片并备份 Flash，下载后逐字节读回，读取一致快照与 PWM 配置并保存证据。
技术栈：Python、pyOCD、IntelHex、CMSIS-DAP、SWD、STM32 官方设备包。
模块联动：flash.ps1 调用下载，gateway.swd 复用会话和快照接口；退出避开探针复位，诊断数据不证明执行器实际动作。
编写/修改日期（日志对应）：2026-10-16（供气演示）；2026-10-15（设备启用和双向联调修正）；2026-09-25；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import time
import weakref
from datetime import datetime
from pathlib import Path

from intelhex import IntelHex
from pyocd.core.helpers import ConnectHelper
from pyocd.flash.file_programmer import FileProgrammer

FIRMWARE = Path(__file__).resolve().parents[1]
PROJECT = FIRMWARE.parents[2]
RUNTIME = PROJECT / ".runtime" / "hardware-test"
FLASH_BASE = 0x08000000
FLASH_SIZE = 65536
MAGIC = 0x5748534B
FIELDS = (
    "magic", "version", "update_count", "sequence", "uptime_ms", "clock_hz",
    "smoke_raw", "temp_raw", "gas_raw", "flame_raw", "smoke_do", "flame_do",
    "alarm", "servo_pulse_us", "gpio_a_output", "gpio_b_output",
    "adc_error_count", "network_ready",
)
# 日志对应：2026-09-22 滤波与换算；2026-09-23 屏幕刷新。兼容旧版状态块，新增字段只读版本 2。
FIELDS_V2 = FIELDS + (
    "filtered_smoke_raw", "filtered_temp_raw", "filtered_gas_raw", "filtered_flame_raw",
    "temperature_centi_c", "temperature_valid", "flame_detected", "filter_count",
    "display_update_count", "processing_test_failures",
)


class ProbeLock:
    """独占本工程探针；操作系统在进程结束时释放，不依赖其他软件目录。
    编写/修改日期（日志对应）：2026-10-15（独立 Keil 包的下载工具可直接导入）。
    """

    def __init__(self, directory: Path):
        """保存锁目录，尚未取得锁时不修改持有者的状态。"""
        self.directory = directory
        self.handle = None

    def acquire(self) -> bool:
        """非阻塞申请一字节文件锁；与网关使用同一路径，冲突时返回 False。"""
        self.directory.mkdir(parents=True, exist_ok=True)
        handle = (self.directory / 'instance.lock').open('a+b')
        if handle.seek(0, 2) == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self.handle = handle
        return True

    def release(self):
        """释放本工具持有的锁并关闭文件；允许重复清理，不改动其他进程记录。"""
        if self.handle is None:
            return
        handle, self.handle = self.handle, None
        try:
            handle.seek(0)
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def open_session(uid: str, resume_on_disconnect: bool = False):
    """固定芯片、设备包和探针，避免自动选择到其他板卡。
    编写/修改日期（日志对应）：2026-09-25。
    """
    pack = RUNTIME / "Keil.STM32F1xx_DFP.2.3.0.pack"
    if not pack.is_file():
        pack = FIRMWARE / 'DeviceSupport' / 'Keil.STM32F1xx_DFP.2.3.0.pack'
    if not pack.is_file():
        raise RuntimeError(f"Missing device pack: {pack}")
    # 日志对应：2026-10-15。下载与网关跨进程独占探针，禁止两条 SWD 会话互相破坏应答。
    probe_lock = ProbeLock(RUNTIME / 'probe-ownership')
    if not probe_lock.acquire():
        raise RuntimeError('调试器正在使用，请先正常停止采集服务，再进行下载或独立诊断')
    try:
        session = ConnectHelper.session_with_chosen_probe(
            blocking=False, unique_id=uid,
            options={
                "target_override": "stm32f103c8", "pack": str(pack),
                "frequency": 500000, "connect_mode": "attach",
                # 日志对应：2026-09-26。ATK 2.1.2 排队传输会应答错位，改用单包同步传输。
                "cmsis_dap.limit_packets": True,
                "cmsis_dap.deferred_transfers": False,
                "resume_on_disconnect": resume_on_disconnect,
            },
        )
    except Exception:
        # 日志对应：2026-10-15。探针枚举失败也释放锁，允许同进程稍后重试。
        probe_lock.release()
        raise
    if session is None:
        probe_lock.release()
        raise RuntimeError(f"Probe is not connected: {uid}")
    session._kitchen_probe_lock = probe_lock
    weakref.finalize(session, probe_lock.release)
    return session


def symbol_address(symbol: str) -> int:
    """从当前编译 MAP 解析状态块地址，避免把旧版固定地址用于新版固件。
    编写/修改日期（日志对应）：2026-09-25。
    """
    map_file = FIRMWARE / "Output" / "atk_f103.map"
    text = map_file.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^\s*" + re.escape(symbol) + r"\s+(0x[0-9a-fA-F]+)\s+Data", text, re.M)
    if not match:
        raise RuntimeError(f"The map file has no {symbol}; rebuild this firmware first")
    return int(match[1], 16)


def status_address() -> int:
    """日志对应：2026-09-25。从本次构建 MAP 取得状态地址，保持旧工具调用兼容。"""
    return symbol_address('g_hardware_status')


def read_status(target, address: int) -> dict:
    """仅接受结构版本匹配、前后计数一致的完整快照，同时读取 CPU 故障寄存器。
    编写/修改日期（日志对应）：2026-09-25。
    """
    for _ in range(20):
        magic, version = target.read_memory_block32(address, 2)
        if magic != MAGIC or version not in (1, 2, 3, 4, 5, 6, 7):
            raise RuntimeError("Firmware status ABI does not match the current build/map")
        fields = (FIELDS_V2 + ('smoke_enabled', 'hazard_flags', 'valve_latched', 'gas_fan_demo_enabled')
                  if version >= 3 else FIELDS_V2 if version == 2 else FIELDS)
        if version >= 4:
            fields += ('control_capabilities', 'command_sequence', 'command_result',
                       'silence_remaining_ms', 'test_remaining_ms', 'rules_revision',
                       'gas_threshold', 'smoke_threshold', 'temperature_threshold_centi')
        if version >= 5:
            fields += ('monitoring_enabled', 'sample_count', 'test_scenario', 'injection_remaining_ms',
                       'effective_gas', 'effective_smoke', 'effective_temperature_centi', 'effective_flame', 'wifi_state', 'arming')
        if version >= 6:
            fields += ('cache_pending', 'cache_capacity', 'cache_dropped', 'boot_identity')
        if version >= 7:
            fields += ('supply_demo_enabled', 'supply_state', 'supply_low_latched', 'supply_low_threshold', 'supply_settle_ms', 'supply_hold_ms')
        values = target.read_memory_block32(address, len(fields))
        after = target.read32(address + 8)
        status = dict(zip(fields, values))
        if status["magic"] != MAGIC or status["version"] != version:
            raise RuntimeError("Firmware status ABI does not match the current build/map")
        if after == status["update_count"] and not after & 1 and after:
            # SWD 返回无符号字，温度是 int32_t，负温必须按补码恢复。
            if status.get('effective_temperature_centi', 0) >= 0x80000000:
                status['effective_temperature_centi'] -= 0x100000000
            if status.get('temperature_centi_c', 0) >= 0x80000000:
                status['temperature_centi_c'] -= 0x100000000
            status.update(
                source="hardware", transport="swd",
                sampled_at=datetime.now().astimezone().isoformat(),
                fault_status=target.read32(0xE000ED28),
                hardfault_status=target.read32(0xE000ED2C),
            )
            return status
        time.sleep(0.05)
    raise RuntimeError("No completed ADC snapshot is available yet")


def collect_status(target, count: int, interval: float, output: Path) -> list[dict]:
    """保存实机样本，并检查采样序号、系统时钟计数继续前进。
    编写/修改日期（日志对应）：2026-09-25。
    """
    address = status_address()
    records = []
    with output.open("w", encoding="utf-8") as stream:
        for index in range(count):
            record = read_status(target, address)
            records.append(record)
            line = json.dumps(record, ensure_ascii=False)
            print(line, flush=True)
            stream.write(line + "\n")
            stream.flush()
            if index + 1 < count:
                time.sleep(interval)
    if len(records) > 1:
        if records[-1]["sequence"] <= records[0]["sequence"]:
            raise RuntimeError("Sampling sequence did not advance during observation")
        if records[-1]["uptime_ms"] <= records[0]["uptime_ms"]:
            raise RuntimeError("System tick did not advance during observation")
    if any(r["fault_status"] or r["hardfault_status"] for r in records):
        raise RuntimeError("CPU fault flags were detected; inspect the saved status log")
    if any(r.get('processing_test_failures', 0) for r in records):
        raise RuntimeError("On-MCU sensor processing self-test failed")
    return records


def inspect_servo(target, output: Path) -> dict:
    """日志对应：2026-09-25。只读核对 PWM 时钟、通道、复用和 PA6 电平，不强制转动舵机。
    """
    registers = {
        'rcc_cfgr': 0x40021004, 'rcc_apb2enr': 0x40021018, 'rcc_apb1enr': 0x4002101C,
        'afio_mapr': 0x40010004, 'gpioa_crl': 0x40010800,
        'tim3_cr1': 0x40000400, 'tim3_ccmr1': 0x40000418, 'tim3_ccer': 0x40000420,
        'tim3_cnt': 0x40000424, 'tim3_psc': 0x40000428, 'tim3_arr': 0x4000042C,
        'tim3_ccr1': 0x40000434,
    }
    values = {name: target.read32(address) for name, address in registers.items()}
    state = read_status(target, status_address())
    prescaler_code = (values['rcc_cfgr'] >> 8) & 7
    apb_divider = 1 if prescaler_code < 4 else 1 << (prescaler_code - 3)
    timer_clock = state['clock_hz'] // apb_divider * (2 if apb_divider > 1 else 1)
    tick_hz = timer_clock / (values['tim3_psc'] + 1)
    high_count, counters = 0, []
    started = time.monotonic()
    for _ in range(80):
        high_count += bool(target.read32(0x40010808) & (1 << 6))
        counters.append(target.read32(0x40000424))
        # 日志对应：2026-09-26。低速取样避开此探针连续密集访问时的应答错位。
        time.sleep(0.027)
    checks = {
        'tim3_clock_enabled': bool(values['rcc_apb1enr'] & 2),
        'gpioa_clock_enabled': bool(values['rcc_apb2enr'] & 4),
        'pa6_alternate_push_pull': (values['gpioa_crl'] >> 24) & 15 in (9, 10, 11),
        'tim3_not_remapped': not ((values['afio_mapr'] >> 10) & 3),
        'counter_enabled': bool(values['tim3_cr1'] & 1),
        'channel1_enabled': bool(values['tim3_ccer'] & 1),
        'channel1_pwm1': (values['tim3_ccmr1'] >> 4) & 7 == 6,
        'counter_advances': len(set(counters)) > 1,
    }
    result = {
        'checked_at': datetime.now().astimezone().isoformat(),
        'registers': {key: hex(value) for key, value in values.items()}, 'checks': checks,
        'period_us': (values['tim3_arr'] + 1) * 1e6 / tick_hz,
        'high_pulse_us': values['tim3_ccr1'] * 1e6 / tick_hz,
        'pa6_high_observations': high_count, 'pa6_low_observations': 80 - high_count,
        'observation_seconds': time.monotonic() - started,
        'status': {key: state[key] for key in ('sequence', 'servo_pulse_us', 'alarm', 'uptime_ms')},
        # 电平抽样不是示波器波形，也不能测量舵机供电、信号幅度或机械位置。
        'physical_motion_verified': False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return result


def flash(session, stamp: str) -> None:
    """先确认芯片容量并备份，再下载、逐字节读回，最后验证应用确实运行。
    编写/修改日期（日志对应）：2026-09-25。
    """
    hex_file = FIRMWARE / "Output" / "atk_f103.hex"
    image = IntelHex(str(hex_file))
    addresses = image.addresses()
    if not addresses or min(addresses) < FLASH_BASE or max(addresses) >= FLASH_BASE + 0xA000:
        raise RuntimeError("HEX is outside this STM32F103C8's 64 KiB Flash")
    # 日志对应：2026-09-26。先确认 HEX 范围与 MAP，错误工程不能进入擦写阶段。
    status_address()
    target = session.target
    device_id = target.read32(0xE0042000)
    capacity_kib = target.read16(0x1FFFF7E0)
    if device_id & 0xFFF != 0x410 or capacity_kib != 64:
        raise RuntimeError(f"Unexpected chip: id={device_id:#x}, Flash={capacity_kib} KiB")
    backup = RUNTIME / f"preflash_{stamp}.bin"
    readback = RUNTIME / f"postflash_{stamp}.bin"
    manifest_path = RUNTIME / f"flash_result_{stamp}.json"
    manifest = {"success": False, "device_id": hex(device_id), "flash_kib": capacity_kib,
                "hex": str(hex_file), "backup": str(backup), "readback": str(readback)}
    try:
        # 日志对应：2026-09-25。复位到线程上下文，避免在中断状态运行 Flash 算法。
        target.reset_and_halt()
        original = bytes(target.read_memory_block8(FLASH_BASE, FLASH_SIZE))
        backup.write_bytes(original)
        manifest["backup_sha256"] = hashlib.sha256(original).hexdigest()
        print(f"Saved original Flash: {backup}", flush=True)
        FileProgrammer(session, chip_erase="sector").program(str(hex_file))
        target.halt()
        actual = bytes(target.read_memory_block8(FLASH_BASE, FLASH_SIZE))
        readback.write_bytes(actual)
        mismatches = [a for a in addresses if actual[a - FLASH_BASE] != image[a]]
        manifest.update(verified_bytes=len(addresses), mismatches=len(mismatches),
                        readback_sha256=hashlib.sha256(actual).hexdigest())
        if mismatches:
            raise RuntimeError(f"Flash verification failed at {mismatches[0]:#x}")
        print(f"Verified {len(addresses)} firmware bytes; no mismatches", flush=True)
        target.reset()
        time.sleep(2)
        status_log = RUNTIME / f"runtime_{stamp}.jsonl"
        records = collect_status(target, 3, 1.2, status_log)
        manifest.update(success=True, runtime_log=str(status_log),
                        sequence_start=records[0]["sequence"], sequence_end=records[-1]["sequence"])
    except Exception as error:
        manifest["error"] = str(error)
        # 日志对应：2026-09-26。下载或校验失败保持暂停，避免启动部分写入的程序。
        try:
            target.halt()
        except Exception:
            pass
        raise
    finally:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Result: {manifest_path}", flush=True)


def main() -> None:
    """flash 执行完整下载验证；status 只观察当前固件，不重写 Flash。
    编写/修改日期（日志对应）：2026-09-25。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("flash", "status", "servo-status"))
    parser.add_argument("--uid", default="ATK-20240820")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--interval", type=float, default=1.2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.samples < 1 or args.interval <= 0:
        parser.error("samples must be positive and interval must be greater than zero")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open_session(args.uid, resume_on_disconnect=args.mode != "flash") as session:
        try:
            if args.mode == "flash":
                flash(session, stamp)
            elif args.mode == "servo-status":
                inspect_servo(session.target, args.output or RUNTIME / f"servo_status_{stamp}.json")
            else:
                output = args.output or RUNTIME / f"hardware_status_{stamp}.jsonl"
                output.parent.mkdir(parents=True, exist_ok=True)
                collect_status(session.target, args.samples, args.interval, output)
                print(f"Saved real hardware samples: {output}", flush=True)
        finally:
            # 日志对应：2026-09-26。ATK 2.1.2 的 DAP_Disconnect 会复位 MCU。
            # 先正常退出 CPU 调试，再关 HID；下载失败仍保留暂停状态。
            session.board.uninit()
            session.probe.close()


if __name__ == "__main__":
    main()
