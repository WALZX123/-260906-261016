/* 文件职责：STM32板载Flash离线采样队列。
 * 功能：575条40字节记录，断线持久化、恢复后补传、ACK后回收；满时保留旧记录并显式计数。
 * 技术栈：C、HAL Flash、12位ADC压缩、FNV完整性摘要、单条确认协议。
 * 联动：demo发布快照，kitchen_wifi传输，gateway/API提交成功才确认；不改变保护输出。
 * 编写/修改日期（日志对应）：2026-10-01、2026-10-15。 */
#include "sample_spool.h"
#include "hardware_status.h"
#include "kitchen_wifi.h"
#include "stm32f1xx_hal.h"
#include <stdio.h>
#include <string.h>
#define BASE 0x0800A000u
#define PAGE_BYTES 1024u
#define PAGE_COUNT 23u
#define PER_PAGE 25u
#define COUNT (PAGE_COUNT*PER_PAGE)
#define MARK 0xA51Du
#define CONFIG 0x0800FC00u
/* 先写数据及摘要，最后提交magic；ACK为独立半字，断电半写记录不会被当成有效。 */
typedef struct {
    uint32_t boot,sequence,uptime,epoch;
    uint8_t adc[12];
    int16_t temperature;
    uint8_t gas,smoke;
    uint16_t flags,checksum,acked,magic;
} StoredSample;
typedef char record_size_must_be_40[(sizeof(StoredSample)==40u)?1:-1];
static uint32_t boot_id,pending_count,dropped_count,next_slot,last_send,inflight=0xFFFFFFFFu;
static uint32_t time_epoch,time_tick;
static StoredSample live;
static uint8_t live_pending;

/* 功能：按页和槽计算地址，保留每页末16字节，不使记录跨擦除页。 */
static const StoredSample *record(uint32_t slot)
{
    return (const StoredSample *)(BASE+(slot/PER_PAGE)*PAGE_BYTES+(slot%PER_PAGE)*sizeof(StoredSample));
}
/* 功能：校验有效载荷，不包含独立ACK和最后提交标记；仅用于完整性。 */
static uint16_t checksum(const StoredSample *value)
{
    const uint8_t *data=(const uint8_t *)value;uint32_t i,hash=2166136261u;
    for(i=0;i<34u;i++) hash=(hash^data[i])*16777619u;
    return (uint16_t)(hash^(hash>>16));
}
/* 功能：只接受已提交、摘要正确的记录，损坏内容不会上传为真实采样。 */
static uint8_t valid(const StoredSample *value)
{
    return value->magic==MARK && value->checksum==checksum(value);
}
/* 功能：保存boot及其反码，配置页重写后启动身份仍单调，不因重连改变。 */
void sample_spool_preserve_boot(void)
{
    HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD,CONFIG+256u,boot_id);
    HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD,CONFIG+260u,~boot_id);
}
/* 功能：扫描启动日志，满时仅整理配置页并保留前256字节；不会擦除采样队列。 */
static void next_boot(void)
{
    uint32_t i,free_address=0u,error;
    static uint32_t config_image[64];
    for(i=256u;i<1024u;i+=8u) {
        const uint32_t *pair=(const uint32_t *)(CONFIG+i);
        if(pair[0]!=0xFFFFFFFFu && pair[1]==~pair[0] && pair[0]>boot_id) boot_id=pair[0];
        if(pair[0]==0xFFFFFFFFu && pair[1]==0xFFFFFFFFu && !free_address) free_address=CONFIG+i;
    }
    boot_id++;
    HAL_FLASH_Unlock();
    if(!free_address) {
        FLASH_EraseInitTypeDef erase={0};
        memcpy(config_image,(const void *)CONFIG,sizeof(config_image));
        erase.TypeErase=FLASH_TYPEERASE_PAGES;erase.PageAddress=CONFIG;erase.NbPages=1u;
        if(HAL_FLASHEx_Erase(&erase,&error)==HAL_OK) {
            for(i=0;i<64u;i++) HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD,CONFIG+i*4u,config_image[i]);
            sample_spool_preserve_boot();
        } else dropped_count++;
    } else {
        if(HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD,free_address,boot_id)!=HAL_OK ||
           HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD,free_address+4u,~boot_id)!=HAL_OK) dropped_count++;
    }
    HAL_FLASH_Lock();
}
/* 功能：上电恢复有效未ACK样本并分配新启动号；未联网也能保留采样顺序。 */
void sample_spool_init(void)
{
    uint32_t i,best_boot=0u,best_sequence=0u;
    for(i=0;i<COUNT;i++) {
        const StoredSample *r=record(i);
        if(valid(r)) {
            if(r->boot>boot_id) boot_id=r->boot;
            if(r->acked!=0u) pending_count++;
            if(r->boot>best_boot || (r->boot==best_boot && r->sequence>=best_sequence)) {
                best_boot=r->boot;best_sequence=r->sequence;next_slot=(i+1u)%COUNT;
            }
        }
    }
    next_boot();
}
/* 功能：每对12位ADC压入3字节，保留原始与滤波四通道而不浪费Flash。 */
static void pack(uint8_t *data,uint16_t a,uint16_t b)
{
    data[0]=(uint8_t)a;data[1]=(uint8_t)((a>>8)|((b&15u)<<4));data[2]=(uint8_t)(b>>4);
}
/* 功能：恢复一对12位量，供补传JSON重建原始通道。 */
static void unpack(const uint8_t *data,uint16_t *a,uint16_t *b)
{
    *a=(uint16_t)(data[0]|((data[1]&15u)<<8));*b=(uint16_t)((data[1]>>4)|(data[2]<<4));
}
/* 功能：有空间才写；擦除页必须没有未ACK记录，容量耗尽时保留旧数据并上报丢弃数。 */
static void persist(StoredSample *value)
{
    uint32_t tries,i,address,error;uint8_t free_slot=0u;
    for(tries=0;tries<COUNT;tries++,next_slot=(next_slot+1u)%COUNT) {
        const uint16_t *words=(const uint16_t *)record(next_slot);
        free_slot=1u;
        for(i=0;i<20u;i++) if(words[i]!=0xFFFFu) {free_slot=0u;break;}
        if(free_slot) break;
        if(next_slot%PER_PAGE==0u) {
            uint8_t reusable=1u;
            for(i=0;i<PER_PAGE;i++) if(valid(record(next_slot+i)) && record(next_slot+i)->acked!=0u) reusable=0u;
            if(reusable) {
                FLASH_EraseInitTypeDef erase={0};
                erase.TypeErase=FLASH_TYPEERASE_PAGES;erase.PageAddress=(uint32_t)record(next_slot);erase.NbPages=1u;
                HAL_FLASH_Unlock();
                free_slot=HAL_FLASHEx_Erase(&erase,&error)==HAL_OK;
                HAL_FLASH_Lock();
                if(free_slot) break;
            }
        }
    }
    if(!free_slot) {dropped_count++;return;}
    value->checksum=checksum(value);value->acked=0xFFFFu;value->magic=MARK;
    address=(uint32_t)record(next_slot);
    HAL_FLASH_Unlock();
    for(i=0;i<18u;i++) if(HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD,address+i*2u,((uint16_t *)value)[i])!=HAL_OK) break;
    if(i==18u && HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD,address+38u,MARK)==HAL_OK) pending_count++;
    else dropped_count++;
    HAL_FLASH_Lock();next_slot=(next_slot+1u)%COUNT;
}
/* 功能：UTC同步后离线按单调计时续算；冷启动未校时返回0，不捏造日期。 */
uint32_t sample_spool_epoch(void) {return time_epoch?time_epoch+(HAL_GetTick()-time_tick)/1000u:0u;}
/* 功能：保存服务器校时基点，只有认证连接的T帧可以调用。 */
void sample_spool_time(uint32_t epoch) {if(epoch>1700000000u) {time_epoch=epoch;time_tick=HAL_GetTick();}}
/* 功能：发布前归档上一条未确认样本，离线样本直接落Flash；待机心跳不占缓存。 */
void sample_spool_capture(void)
{
    volatile HardwareTestStatus *s=&g_hardware_status;
    if(live_pending) {persist(&live);live_pending=0u;}
    if(!s->monitoring_enabled) return;
    memset(&live,0,sizeof(live));
    live.boot=boot_id;live.sequence=s->sequence;live.uptime=s->uptime_ms;live.epoch=sample_spool_epoch();
    pack(live.adc,(uint16_t)s->smoke_raw,(uint16_t)s->temp_raw);pack(live.adc+3,(uint16_t)s->gas_raw,(uint16_t)s->flame_raw);
    pack(live.adc+6,(uint16_t)s->filtered_smoke_raw,(uint16_t)s->filtered_temp_raw);pack(live.adc+9,(uint16_t)s->filtered_gas_raw,(uint16_t)s->filtered_flame_raw);
    live.temperature=s->effective_temperature_centi==(int32_t)0x80000000?(int16_t)-32768:(int16_t)s->effective_temperature_centi;
    live.gas=(uint8_t)s->effective_gas;live.smoke=(uint8_t)s->effective_smoke;
    live.flags=(uint16_t)(1u|(s->effective_flame?2u:0u)|(s->smoke_do?4u:0u)|(s->flame_do?8u:0u)|
        (s->valve_latched?16u:0u)|((s->gpio_a_output&(1u<<8))?32u:0u)|((s->gpio_b_output&1u)?64u:0u)|
        ((s->gpio_b_output&(1u<<12))?128u:0u)|(s->adc_error_count?256u:0u)|((s->test_scenario&7u)<<10)|((s->hazard_flags&3u)<<13));
    if(g_wifi_config.state==5u) live_pending=1u;else persist(&live);
}
/* 功能：服务器提交后才确认；只匹配当前在途缓存或当前实时样本，重复帧不误删其他样本。 */
void sample_spool_ack(uint32_t boot,uint32_t sequence)
{
    if(live_pending && live.boot==boot && live.sequence==sequence) live_pending=0u;
    if(inflight<COUNT) {
        const StoredSample *r=record(inflight);
        if(r->boot==boot && r->sequence==sequence && r->acked!=0u) {
            HAL_FLASH_Unlock();
            if(HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD,(uint32_t)&r->acked,0u)==HAL_OK) {if(pending_count) pending_count--;inflight=0xFFFFFFFFu;}
            HAL_FLASH_Lock();
        }
    }
}
/* 功能：每200ms最多补一条，未收到确认一秒后重发；启动号和序号在数据库去重。 */
void sample_spool_step(void)
{
    static char line[850];uint32_t i,now=HAL_GetTick(),best_boot=0xFFFFFFFFu,best_seq=0xFFFFFFFFu;
    const StoredSample *r;uint16_t raw[4],filtered[4];char temp[16];int length;
    uint16_t flags;uint8_t scenario,hazards;
    if(g_wifi_config.state!=5u || !pending_count || now-last_send<200u) return;
    if(inflight<COUNT && now-last_send<1000u) return;
    if(inflight>=COUNT) for(i=0;i<COUNT;i++) {
        const StoredSample *v=record(i);
        if(valid(v) && v->acked!=0u && (v->boot<best_boot || (v->boot==best_boot && v->sequence<best_seq))) {
            best_boot=v->boot;best_seq=v->sequence;inflight=i;
        }
    }
    if(inflight>=COUNT) return;
    r=record(inflight);flags=r->flags;scenario=(uint8_t)((flags>>10)&7u);hazards=(uint8_t)((flags>>13)&3u);
    unpack(r->adc,raw,raw+1);unpack(r->adc+3,raw+2,raw+3);unpack(r->adc+6,filtered,filtered+1);unpack(r->adc+9,filtered+2,filtered+3);
    if(r->temperature==-32768) snprintf(temp,sizeof(temp),"null");
    else {uint32_t n=(uint32_t)(r->temperature<0?-r->temperature:r->temperature);
        snprintf(temp,sizeof(temp),"%s%lu.%02lu",r->temperature<0?"-":"",(unsigned long)(n/100u),(unsigned long)(n%100u));}
    length=snprintf(line,sizeof(line),"{\"type\":\"backfill\",\"boot_id\":\"mcu-%lu\",\"sequence\":%lu,\"sampled_unix\":%lu,\"device_uptime_ms\":%lu,\"sampled_at\":\"1970-01-01T00:00:00Z\",\"gas\":%u,\"smoke\":%u,\"temperature\":%s,\"flame\":%s,\"valid\":false,\"io_valid\":%s,\"local_alarm\":\"%s\",\"monitoring_enabled\":true,\"test_scenario\":\"%s\",\"backfilled\":true,\"transport\":\"tcp\",\"firmware\":\"stm32f103-hwtest/6.0\",\"raw\":{\"smoke_ao\":%u,\"temp_ao\":%u,\"gas_ao\":%u,\"flame_ao\":%u,\"smoke_do\":%u,\"flame_do\":%u},\"filtered\":{\"smoke_ao\":%u,\"temp_ao\":%u,\"gas_ao\":%u,\"flame_ao\":%u},\"actuators\":{\"valve\":\"%s\",\"fan\":\"%s\",\"buzzer\":\"%s\",\"power\":\"%s\"}}\r\n",
        (unsigned long)r->boot,(unsigned long)r->sequence,(unsigned long)r->epoch,(unsigned long)r->uptime,r->gas,r->smoke,temp,
        flags&2u?"true":"false",flags&256u?"false":"true",hazards==3u?"multiple":hazards==2u?"fire":hazards==1u?"gas":(flags&256u || r->temperature==-32768)?"sensor_fault":"normal",
        scenario==1u?"gas":scenario==2u?"smoke":scenario==3u?"temperature":scenario==4u?"flame":scenario==5u?"multiple":"",
        raw[0],raw[1],raw[2],raw[3],(flags&4u)?1u:0u,(flags&8u)?1u:0u,filtered[0],filtered[1],filtered[2],filtered[3],
        flags&16u?"closed":"open",flags&32u?"on":"off",flags&64u?"on":"off",flags&128u?"on":"off");
    if(length>0 && length<(int)sizeof(line)) {kitchen_wifi_send(line,(uint16_t)length);last_send=now;}
}
/* 以下只读诊断供OLED之外的PC界面展示，不影响控制逻辑。 */
uint32_t sample_spool_boot(void) {return boot_id;}
uint32_t sample_spool_pending(void) {return pending_count;}
uint32_t sample_spool_capacity(void) {return COUNT;}
uint32_t sample_spool_dropped(void) {return dropped_count;}
