@echo off
chcp 936 > nul
rem 文件职责：Keil内的一键实机下载入口。
rem 功能：调用同一pyOCD安全参数，备份、烧录、读回并复位运行；关联hardware_test.py。
rem 技术栈：Windows批处理、Python、CMSIS-DAP；编写/修改日期（日志对应）：2026-10-15。
setlocal
if "%~1"=="--check" (
 echo [KEIL DOWNLOAD] Entry point ready.
 exit /b 0
)
set "KITCHEN_PROJECT=%~dp0..\..\..\.."
set "KITCHEN_PYTHON=%KITCHEN_PROJECT%\.venv\Scripts\python.exe"
if not exist "%KITCHEN_PYTHON%" (
 echo ERROR: Project Python environment missing. Create .venv in the project root first.
 exit /b 2
)
echo [KEIL DOWNLOAD] Backup, program, verify and run STM32F103C8.
"%KITCHEN_PYTHON%" -X utf8 "%~dp0hardware_test.py" flash
if errorlevel 1 exit /b 1
echo [KEIL DOWNLOAD] Verified firmware is running. OLED starts in standby.
exit /b 0
