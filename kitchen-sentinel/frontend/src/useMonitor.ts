// 监控数据优先使用 WebSocket 推送，定时 REST 查询作为断线兜底。
import {useCallback,useEffect,useRef,useState} from 'react';
import {api} from './api';
import type {Snapshot,Sample} from './types';
export function useMonitor(enabled:boolean){
 const [snapshot,setSnapshot]=useState<Snapshot|null>(null),[samples,setSamples]=useState<Sample[]>([]),[connected,setConnected]=useState(false),[error,setError]=useState('');
 const recent=useRef<string>('');
 const refresh=useCallback(async()=>{try{setSnapshot(await api<Snapshot>('/snapshot'));setError('')}catch(e){setError((e as Error).message)}},[]);
 useEffect(()=>{if(!enabled)return;let stopped=false,socket:WebSocket,retry:ReturnType<typeof setTimeout>;
  api<Sample[]>('/telemetry?limit=90').then(setSamples).catch(()=>{});
  // WebSocket 是实时展示通道，查询接口仍作为兜底；这样页面短暂断线时不会把旧状态当成实时状态。
  const connect=()=>{try{socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/v1/live`);}catch(e){setConnected(false);setError('实时连接创建失败，正在重试');if(!stopped)retry=setTimeout(connect,3000);return;}
   socket.onopen=()=>{setConnected(true);setError('')};
   socket.onmessage=(e)=>{try{const data=JSON.parse(e.data) as Snapshot;setSnapshot(data);const s=data.devices[0]?.latest;if(s?.sampled_at&&s.sampled_at!==recent.current){recent.current=s.sampled_at;setSamples(prev=>[...prev,s as Sample].slice(-90))}}catch{setError('实时数据格式异常，正在等待下一条数据')}};
   // 采用固定退避间隔，避免网络恢复时反复快速重连占满服务端连接。
   socket.onclose=()=>{setConnected(false);if(!stopped)retry=setTimeout(connect,3000)};
   socket.onerror=()=>setConnected(false);
  }; connect();void refresh();const fallback=setInterval(()=>void refresh(),10000);
  return()=>{stopped=true;clearTimeout(retry);clearInterval(fallback);socket?.close()};
 },[enabled,refresh]);
 return {snapshot,samples,connected,error,refresh};
}
