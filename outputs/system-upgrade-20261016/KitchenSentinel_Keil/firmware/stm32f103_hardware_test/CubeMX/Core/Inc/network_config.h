/*
 * 文件职责：保留旧版本无线配置宏的兼容声明。
 * 主要功能：旧接口使用空值；当前运行通过 kitchen_wifi 的 RAM 配置与 Flash 配置页管理网络。
 * 技术栈：C 预处理宏；模块联动：当前 Users/kitchen_wifi.c 和 gateway/wifi_config.py。
 * 编写/修改日期（日志对应）：2026-09-30、2026-10-15（无线参数改为私有配置，不在源码保存密码）。
 */
#ifndef KITCHEN_NETWORK_CONFIG_H
#define KITCHEN_NETWORK_CONFIG_H

/* 日志对应：2026-10-15。历史宏不再用于当前连接，保持空值。
 * 请在网页“设备启用”维护网络配置，禁止把热点密码或认证密钥写入可分享的源码。 */
#define KITCHEN_WIFI_SSID ""
#define KITCHEN_WIFI_PASSWORD ""
#define KITCHEN_TCP_SERVER_IP ""
#define KITCHEN_TCP_SERVER_PORT "9000"

#endif
