"""文件职责：STM32 实物网关包入口。
主要功能：组织 SWD 读取、TCP 接入和统一帧协议。
技术栈：Python、pyOCD、asyncio、HTTPX。
模块联动：swd 与 server 使用独立硬件身份向 backend.api.devices 上报，protocol 校验 TCP 帧。
编写/修改日期（日志对应）：2026-09-30。
"""
