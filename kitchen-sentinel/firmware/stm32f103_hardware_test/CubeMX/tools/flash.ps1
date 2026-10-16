<#
文件职责：Keil 编译与实物下载的串联入口。
主要功能：定位工程和虚拟环境，编译成功后再执行备份、烧录、逐字节校验和运行检查。
技术栈：PowerShell、Keil MDK/ARMCC、Python、pyOCD、CMSIS-DAP。
模块联动：编译 atk_f103.uvprojx，再调用 hardware_test.py；使用前先退出占用探针的采集进程。
编写/修改日期（日志对应）：2026-09-25。
#>
param([string]$Keil = 'C:\Keil_v5\UV4\uVision.com')
# 日志对应：2026-09-25 本地端功能自测。先编译，再备份、下载、逐字节校验与实机采样。
$ErrorActionPreference = 'Stop'
$firmwareRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $firmwareRoot))
$projectFile = Join-Path $firmwareRoot 'MDK-ARM\KitchenSentinel_F103.uvprojx'
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $Keil)) { throw "Keil compiler not found: $Keil" }
if (!(Test-Path -LiteralPath $python)) { throw "Project Python environment not found: $python" }
# 编译失败立即停止，避免把旧 HEX 当作刚修改的固件下载。
& $Keil -b $projectFile -t Template
if ($LASTEXITCODE -ne 0) { throw "Keil build failed, exit code $LASTEXITCODE" }
& $python (Join-Path $PSScriptRoot 'hardware_test.py') flash
if ($LASTEXITCODE -ne 0) { throw "Flash or real hardware verification failed, exit code $LASTEXITCODE" }
