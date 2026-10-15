@echo off
rem 文件职责：无线运行快捷入口；主要功能：启动网页与 Wi-Fi 网关，不占用调试器。
rem 技术栈：Windows CMD、项目 Python；模块联动：start.py 和已配置的 MB026。
rem 编写/修改日期（日志对应）：2026-10-15。
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" "%~dp0start.py" --wifi-only
pause
