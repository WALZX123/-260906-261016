/*
 * 文件职责：MB026 无线连接参数。
 * 主要功能：集中提供 Wi-Fi、TCP 服务器和端口的编译配置，空配置时维持本地采样。
 * 技术栈：C 预处理宏、MB026 AT 指令与 TCP 透传。
 * 模块联动：demo_run 判断配置是否完整再调用 ATK_MB026 驱动；填入参数不等于链路已验证，凭据不进入日志。
 * 编写/修改日期（日志对应）：2026-09-30。
 */
#ifndef KITCHEN_NETWORK_CONFIG_H
#define KITCHEN_NETWORK_CONFIG_H

/* 日志对应：2026-09-30 设备接入与数据上报。
 * 填入实际 2.4 GHz Wi-Fi 和电脑局域网 IPv4 后重新编译，才能测试 TCP 上报。
 * 默认留空，采样和本地输出仍运行；此配置不表示无线链路已经测试通过。 */
#define KITCHEN_WIFI_SSID ""
#define KITCHEN_WIFI_PASSWORD ""
#define KITCHEN_TCP_SERVER_IP ""
#define KITCHEN_TCP_SERVER_PORT "9000"

#endif
