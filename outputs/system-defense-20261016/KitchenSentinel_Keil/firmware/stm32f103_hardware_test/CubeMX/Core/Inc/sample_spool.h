/* 文件职责：板载Flash离线采样存档接口。
 * 功能：压缩、校验、掉电恢复、服务器确认后删除及有限容量诊断。
 * 技术栈：STM32F1 Flash、40字节记录、CRC式摘要；联动demo、kitchen_wifi和补传API。
 * 编写/修改日期（日志对应）：2026-10-01、2026-10-15。 */
#ifndef SAMPLE_SPOOL_H
#define SAMPLE_SPOOL_H
#include <stdint.h>
/* OLED点亮后初始化，扫描缓存并分配持久启动身份。 */
void sample_spool_init(void);
/* 每次500ms遥测发布前调用；只存启用采样，未确认记录不得静默覆盖。 */
void sample_spool_capture(void);
/* 每轮推进一条补传，实时保护和实时遥测优先。 */
void sample_spool_step(void);
/* 只接受服务器提交成功后的启动号+序号确认，重复确认幂等。 */
void sample_spool_ack(uint32_t boot,uint32_t sequence);
/* 同步服务器UTC秒，离线期间由单调毫秒计数推算。 */
void sample_spool_time(uint32_t epoch);
/* 配置页重写时保留当前启动计数，调用者须已解锁Flash。 */
void sample_spool_preserve_boot(void);
/* 返回本轮身份、UTC秒、待上传数、容量与溢出/存储错误，供诊断和协议使用。 */
uint32_t sample_spool_boot(void);
uint32_t sample_spool_epoch(void);
uint32_t sample_spool_pending(void);
uint32_t sample_spool_capacity(void);
uint32_t sample_spool_dropped(void);
#endif
