"""总入口的子进程生命周期管理。

Windows 的虚拟环境 Python 会再启动基础解释器，只结束 Popen 对象可能
留下子进程。Job Object 将进程树绑定到入口句柄，强制结束入口时系统也
会清理该树。管理器只管理自己创建的进程，不批量结束其他 Python 程序。
"""
from __future__ import annotations

import contextlib
import os
import signal
import subprocess
from pathlib import Path


class ProcessSupervisor:
    """管理本次启动的进程，按逆序关闭，超时后强制回收。"""

    def __init__(self) -> None:
        self.processes: list[subprocess.Popen] = []
        try:
            self._job = WindowsJob() if os.name == 'nt' else None
        except OSError:
            # 某些 IDE 已把当前 Python 放入受限 Job，无法嵌套时退回 taskkill。
            self._job = None

    def spawn(self, command: list[str], cwd: Path, env: dict | None = None) -> subprocess.Popen:
        """创建独立进程组并登记所有权，方便退出信号和强制清理。"""
        process = subprocess.Popen(
            command, cwd=cwd, env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
            start_new_session=os.name != 'nt',
        )
        self.processes.append(process)
        if self._job:
            try:
                self._job.assign(process)
            except OSError:
                self._job.close()
                self._job = None
        return process

    def close(self) -> None:
        """先请求正常结束；等待超时后回收本次启动的进程树。"""
        for process in reversed(self.processes):
            if process.poll() is None:
                with contextlib.suppress(OSError):
                    if os.name == 'nt':
                        process.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        os.killpg(process.pid, signal.SIGTERM)
        for process in reversed(self.processes):
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=3)
        if self._job:
            self._job.close()
        else:
            for process in reversed(self.processes):
                if process.poll() is None:
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], check=False,
                                       capture_output=True)
                    else:
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGKILL)
        for process in self.processes:
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=3)


class WindowsJob:
    """封装 Windows Job Object，句柄关闭时结束其中所有进程。"""

    def __init__(self) -> None:
        # 仅在 Windows 初始化，其他系统不需要加载 Win32 的结构与 DLL。
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                ('flags', wintypes.DWORD), ('min_working_set', ctypes.c_size_t),
                ('max_working_set', ctypes.c_size_t), ('active_processes', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                ('scheduling', wintypes.DWORD),
            ]

        class IOCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                'read_operations', 'write_operations', 'other_operations',
                'read_bytes', 'write_bytes', 'other_bytes',
            )]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ('basic', BasicLimits), ('io', IOCounters),
                ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t),
            ]

        self._api = ctypes.WinDLL('kernel32', use_last_error=True)
        self._api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self._api.CreateJobObjectW.restype = wintypes.HANDLE
        self._api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self._api.SetInformationJobObject.restype = wintypes.BOOL
        self._api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._api.AssignProcessToJobObject.restype = wintypes.BOOL
        self._api.CloseHandle.argtypes = [wintypes.HANDLE]
        self._api.CloseHandle.restype = wintypes.BOOL
        self._handle = self._api.CreateJobObjectW(None, None)
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE。
        if not self._api.SetInformationJobObject(self._handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, process: subprocess.Popen) -> None:
        """将刚启动的进程及其后续子进程加入作业对象。"""
        import ctypes
        if not self._api.AssignProcessToJobObject(self._handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        """释放作业句柄；重复调用也安全。"""
        if self._handle:
            self._api.CloseHandle(self._handle)
            self._handle = None
