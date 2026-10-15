/**
 * 文件职责：实时监控订阅与断线恢复。
 * 主要功能：订阅设备和报警更新，以两秒查询兜底，识别连接停滞、迟到快照及重复采样。
 * 技术栈：React Hooks、WebSocket、Fetch、AbortController、浏览器可见性事件。
 * 模块联动：App 默认订阅实物，系统测试页独立订阅测试节点；采样身份保持曲线一致。
 * 编写/修改日期（日志对应）：2026-10-01、2026-10-13（实时性与恢复优化）。
 */
import {useCallback,useEffect,useRef,useState} from 'react';
import {api} from './api';
import type {Snapshot,Sample} from './types';

/** 订阅指定来源，收到消息才视为实时连接可用；离开或注销时取消所有资源。
 * 编写/修改日期（日志对应）：2026-10-13。 */
export function useMonitor(enabled:boolean,scope:'hardware'|'simulated'|'all'='hardware'){
 const [snapshot,setSnapshot]=useState<Snapshot|null>(null),[samples,setSamples]=useState<Sample[]>([]);
 const [connected,setConnected]=useState(false),[error,setError]=useState(''),[updatedAt,setUpdatedAt]=useState<number|null>(null);
 const receiver=useRef<(data:Snapshot)=>void>(()=>{}),epoch=useRef(0);
 /** REST 刷新与重连共用入口，过期请求不能更新已注销或切换来源的页面。
  * 编写/修改日期（日志对应）：2026-10-13。 */
 const refresh=useCallback(async()=>{
  const current=epoch.current;
  try{const data=await api<Snapshot>('/snapshot?scope='+scope,{signal:AbortSignal.timeout(6000)});if(current===epoch.current){receiver.current(data);setError('')}}
  catch(e){if(current===epoch.current)setError((e as Error).message)}
 },[scope]);
 /** 统一接受快照和追加曲线，监测心跳、断线补查及前后台切换。
  * 编写/修改日期（日志对应）：2026-10-13。 */
 useEffect(()=>{
  epoch.current++;
  if(!enabled){setSnapshot(null);setSamples([]);setConnected(false);setUpdatedAt(null);return}
  let stopped=false,socket:WebSocket|undefined,retry:ReturnType<typeof setTimeout>|undefined;
  let lastMessage=0,lastServer=0,polling=false,lastSample='',deviceId='';
  const controller=new AbortController();
  /** 历史和实时按启动编号、序号去重，避免首屏历史覆盖新采样。
   * 编写/修改日期（日志对应）：2026-10-13。 */
  const merge=(rows:Sample[])=>setSamples(prev=>{
   const unique=new Map<string,Sample>();
   for(const row of [...prev,...rows])unique.set((row.device_id||deviceId)+':'+(row.boot_id||'')+':'+(row.sequence??row.sampled_at),row);
   return [...unique.values()].sort((a,b)=>Date.parse(a.sampled_at)-Date.parse(b.sampled_at)).slice(-90);
  });
  receiver.current=data=>{
   if(stopped||Date.parse(data.server_time)<lastServer)return;
   lastServer=Date.parse(data.server_time);setSnapshot(data);setUpdatedAt(Date.now());
   const device=data.devices[0],sample=device?.latest;
   if(device?.id!==deviceId){deviceId=device?.id||'';lastSample='';setSamples([]);
    if(deviceId)void api<Sample[]>('/telemetry?device_id='+encodeURIComponent(deviceId)+'&limit=90',{signal:controller.signal})
     .then(rows=>{if(!stopped&&deviceId===device?.id)merge(rows)}).catch(()=>{});
   }
   const identity=deviceId+':'+sample?.boot_id+':'+(sample?.sequence??sample?.sampled_at);
   if(sample?.sampled_at&&identity!==lastSample){lastSample=identity;merge([{...sample,device_id:deviceId} as Sample])}
  };
  /** 消息到达才置为在线；关闭后统一退避重连，避免错误与关闭安排双重计时。
   * 编写/修改日期（日志对应）：2026-10-13。 */
  const connect=()=>{
   if(stopped)return;
   try{socket=new WebSocket((location.protocol==='https:'?'wss':'ws')+'://'+location.host+'/api/v1/live?scope='+scope)}
   catch{retry=setTimeout(connect,1000);return}
   socket.onmessage=e=>{if(stopped)return;try{receiver.current(JSON.parse(e.data) as Snapshot);lastMessage=Date.now();setConnected(true);setError('')}catch{setError('实时数据格式异常，正在重新获取')}};
   socket.onclose=()=>{if(stopped)return;setConnected(false);clearTimeout(retry);retry=setTimeout(connect,1000)};
   socket.onerror=()=>socket?.close();
  };
  /** 兜底请求只运行一份；失败保留最后读数并显示可读错误。
   * 编写/修改日期（日志对应）：2026-10-13。 */
  const poll=async()=>{if(polling||stopped)return;polling=true;try{await refresh()}finally{polling=false}};
  /** 联网或从后台返回时马上补取数据。
   * 编写/修改日期（日志对应）：2026-10-13。 */
  const resume=()=>{if(document.visibilityState==='visible')void poll()};
  connect();void poll();
  const fallback=setInterval(()=>{if(Date.now()-lastMessage>3500){setConnected(false);void poll();if(socket?.readyState===WebSocket.OPEN)socket.close()}},2000);
  window.addEventListener('online',resume);document.addEventListener('visibilitychange',resume);
  return()=>{stopped=true;epoch.current++;receiver.current=()=>{};controller.abort();clearTimeout(retry);clearInterval(fallback);socket?.close();window.removeEventListener('online',resume);document.removeEventListener('visibilitychange',resume)};
 },[enabled,scope,refresh]);
 return {snapshot,samples,connected,error,refresh,updatedAt};
}
