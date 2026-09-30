"""本机监听端口选择，不终止已有服务，也不放宽套接字独占限制。"""

import errno
import socket
import sys


def select_port(host: str, preferred: int, attempts: int = 20) -> tuple[int, str | None]:
    """检查首选端口；遇到占用或系统限制时顺序尝试其他端口。

    Windows 独占绑定可能被监听进程、尚未释放的旧连接或保留端口拒绝。
    不能一律声称有进程占用，也不能结束其他服务来取得端口。返回首个
    可绑定端口和首选失败原因，让总入口向用户显示真实访问地址。
    该探测只能反映当前状态，探测后被其他进程抢占仍由 Uvicorn 报告。
    """
    first_reason = None
    for port in range(preferred, min(preferred + attempts, 65536)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if sys.platform == 'win32':
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                probe.bind((host, port))
                return port, first_reason
            except OSError as exc:
                code = getattr(exc, 'winerror', None) or exc.errno
                if code in (10048, errno.EADDRINUSE):
                    reason = '端口已占用或旧连接尚未释放'
                elif code in (10013, errno.EACCES):
                    reason = '端口受系统保留或访问权限限制'
                else:
                    # 非端口原因（例如主机名无法解析）不能靠递增端口解决。
                    raise RuntimeError(f'监听地址 {host} 不可用（系统错误 {code}）：{exc}') from exc
                if first_reason is None:
                    first_reason = f'{reason}（系统错误 {code}）'
    raise RuntimeError(
        f'{host} 从 {preferred} 开始的 {min(attempts, 65536 - preferred)} 个端口均不可用：'
        f'{first_reason}。请使用 --port 指定其他端口。'
    )
