"""文件职责：Keil外部下载命令适配。
功能：统一输出流，避免调试器INFO/进度在stderr被Keil误判为构建错误；保留真实失败退出码。
技术栈：Python、pyOCD；关联hardware_test备份/下载/读回/复位运行流程。
编写/修改日期（日志对应）：2026-10-15。
"""
import sys


def download():
    """Keil专用入口不吞异常：诊断与进度进stdout，真正异常仍以非零退出码停止构建。"""
    sys.stderr = sys.stdout
    from hardware_test import main
    sys.argv = [sys.argv[0], 'flash']
    main()


if __name__ == '__main__':
    download()
