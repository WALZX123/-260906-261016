"""文件职责：数据库提交后的实时更新通知。
主要功能：用线程安全版本号唤醒监控连接，支持超时心跳和多个浏览器独立订阅。
技术栈：Python threading.Condition、单调递增版本号。
模块联动：core.db 在事务真正提交后发布版本，main.live 等待版本后读取快照；不传递未提交数据。
编写/修改日期（日志对应）：2026-10-01、2026-10-13（实时推送优化）。
"""
from threading import Condition


class LiveUpdates:
    """保存本进程更新版本；每个连接保存自己的游标，避免一个客户端消耗其他客户端通知。
    编写/修改日期（日志对应）：2026-10-13。
    """

    def __init__(self):
        """初始化同步条件和版本；锁内只改计数，不进行数据库查询。
        编写/修改日期（日志对应）：2026-10-13。
        """
        self.condition = Condition()
        self.revision = 0

    def publish(self):
        """事务提交后递增版本并唤醒全部等待连接。
        编写/修改日期（日志对应）：2026-10-13。
        """
        with self.condition:
            self.revision += 1
            self.condition.notify_all()

    def wait(self, previous, timeout=1.0):
        """等待新版本或心跳超时，返回当前版本；连续提交可合并为最新状态。
        编写/修改日期（日志对应）：2026-10-13。
        """
        with self.condition:
            self.condition.wait_for(lambda: self.revision != previous, timeout=timeout)
            return self.revision


updates = LiveUpdates()
