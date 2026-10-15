"""文件职责：项目单实例启动锁。
主要功能：跨进程独占同一项目目录，保存访问地址，重复启动复用原实例而不新开另一个端口。
技术栈：Python、Windows msvcrt 文件锁（其他系统使用 flock）、本地 JSON。
模块联动：start 在启动任何子进程和清理退出标记前取得锁；main 健康接口报告项目标识与版本。
编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-10-10、2026-10-12。
"""
import hashlib
import json
import os
import sys
from pathlib import Path

from scripts.runtime import PROJECT_ROOT

APP_VERSION = '1.2.0'
PROJECT_ID = hashlib.sha256(str(PROJECT_ROOT.resolve()).casefold().encode()).hexdigest()[:16]


class ProjectInstance:
    """持有真正的进程文件锁；进程退出时操作系统会释放锁，不依赖容易陈旧的 PID 文件判断。
    编写/修改日期（日志对应）：2026-10-12。
    """

    def __init__(self, directory: Path):
        """日志对应：2026-10-12。保存运行目录，锁成功前不改动现有实例的记录。"""
        self.directory, self.handle = directory, None

    def acquire(self):
        """日志对应：2026-10-12。非阻塞取得一字节独占锁，已占用时返回 False。"""
        self.directory.mkdir(exist_ok=True, parents=True)
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

    def record(self, url, mode):
        """日志对应：2026-10-12。锁持有者原子写访问资料，不包含账号、密码或设备令牌。"""
        temporary = self.directory / 'instance.json.tmp'
        temporary.write_text(json.dumps({'url': url, 'mode': mode, 'pid': os.getpid(),
            'project_id': PROJECT_ID, 'version': APP_VERSION}), encoding='utf-8')
        temporary.replace(self.directory / 'instance.json')

    def existing_url(self):
        """日志对应：2026-10-12。仅接受本机 URL，损坏记录不启动重复实例，也不打开外部网址。"""
        from urllib.parse import urlsplit
        try:
            data = json.loads((self.directory / 'instance.json').read_text(encoding='utf-8'))
            url = data['url']
            parsed = urlsplit(url)
            if parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1') and parsed.port:
                return url
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return None

    def release(self):
        """日志对应：2026-10-12。只移除自身运行记录并释放锁，不修改其他实例的退出通知。"""
        if self.handle is not None:
            (self.directory / 'instance.json').unlink(missing_ok=True)
            self.handle.seek(0)
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None
