/** 文件职责：浏览器提示音与桌面通知运行层。
 * 主要功能：普通页面交互自动恢复音频、读取实际授权、提交通知及提供可观察的自检计数。
 * 技术栈：Web Audio、Notification、Permissions、DOM事件；关联AlarmNotifier和通知设置。
 * 编写/修改日期（日志对应）：2026-10-13、2026-10-16。偏好由服务器保存，本层不伪造浏览器授权。 */

/** 运行状态与用户开关独立；提交计数不代表操作系统已展示横幅或扬声器实际可闻。 */
export interface NotificationRuntimeState {
 audio:'waiting'|'ready'|'unsupported'|'error';
 permission:NotificationPermission|'unsupported';
 tonesPlayed:number;
 notificationsSubmitted:number;
 error:string;
}

let state:NotificationRuntimeState={audio:'waiting',permission:'unsupported',tonesPlayed:0,notificationsSubmitted:0,error:''};
const subscribers=new Set<()=>void>();
const activeNotifications=new Set<Notification>();
let context:AudioContext|null=null,installed=false,wantsSound=false,pendingTone=false;

/** 保持同一对象直到状态变化，供React外部订阅，避免读取快照产生无限重渲染。 */
function publish(patch:Partial<NotificationRuntimeState>){
 const next={...state,...patch};
 if(Object.keys(next).every(key=>next[key as keyof NotificationRuntimeState]===state[key as keyof NotificationRuntimeState]))return;
 state=next;subscribers.forEach(listener=>listener());
}

/** 向组件提供只读快照与订阅清理，不写业务状态。 */
export const notificationRuntime={getSnapshot:()=>state,subscribe:(listener:()=>void)=>{subscribers.add(listener);return()=>{subscribers.delete(listener)}}};

/** 同步浏览器的真实权限；没有授权时绝不显示为已开启。 */
export function refreshNotificationPermission(){
 publish({permission:'Notification' in window?Notification.permission:'unsupported'});
}

/** 创建或恢复静音音频上下文；普通登录/切页点击即可唤醒，不要求重新设置通知开关。 */
function prepareAudio(){
 if(!('AudioContext' in window)){publish({audio:'unsupported'});return}
 try{
  if(!context||context.state==='closed'){
   context=new AudioContext();
   context.onstatechange=()=>publish({audio:context?.state==='running'?'ready':'waiting'});
  }
  if(context.state==='running'){publish({audio:'ready'});return}
  // 自动播放受限时resume可能等待下一次用户交互；不阻塞登录、监测或数据库请求。
  void context.resume().then(()=>{
   publish({audio:context?.state==='running'?'ready':'waiting',error:''});
   if(pendingTone&&wantsSound){pendingTone=false;playAlertTone()}
  }).catch(()=>publish({audio:'waiting'}));
 }catch{publish({audio:'error',error:'浏览器音频初始化未完成'})}
}

/** 页面生命周期只安装一次；登录按钮、导航、键盘操作均可恢复浏览器允许的音频。 */
export function installNotificationRuntime(){
 if(installed)return;
 installed=true;refreshNotificationPermission();
 window.addEventListener('pointerdown',prepareAudio,{capture:true,passive:true});
 window.addEventListener('keydown',prepareAudio,{capture:true,passive:true});
 window.addEventListener('focus',refreshNotificationPermission);
 document.addEventListener('visibilitychange',refreshNotificationPermission);
 if(!('AudioContext' in window))publish({audio:'unsupported'});
 if(navigator.permissions)void navigator.permissions.query({name:'notifications'}).then(permission=>{
  permission.onchange=refreshNotificationPermission;
 }).catch(()=>{});
}

/** 仅在已读取账号设置后启用音频；关闭偏好时撤销尚未播放的提示。 */
export function configureNotificationSound(enabled:boolean){
 wantsSound=enabled;
 if(enabled)prepareAudio();else pendingTone=false;
}

/** 播放短提示并释放音频节点；输出计数用于系统测试，不替代实物蜂鸣器或扬声器验收。 */
export function playAlertTone(){
 if(!wantsSound)return false;
 if(!context||context.state!=='running'){pendingTone=true;prepareAudio();return false}
 try{
  const oscillator=context.createOscillator(),gain=context.createGain();
  oscillator.frequency.value=880;gain.gain.setValueAtTime(.12,context.currentTime);
  gain.gain.exponentialRampToValueAtTime(.001,context.currentTime+.45);
  oscillator.connect(gain);gain.connect(context.destination);
  oscillator.onended=()=>{oscillator.disconnect();gain.disconnect()};
  oscillator.start();oscillator.stop(context.currentTime+.45);
  publish({tonesPlayed:state.tonesPlayed+1,error:''});return true;
 }catch{publish({error:'提示音播放未完成'});return false}
}

/** 异常已恢复或确认时清除待唤醒提示，防止下次点击补播过时报警。 */
export function clearPendingTone(){pendingTone=false}

/** 首次授权只能由明确点击触发；已有授权直接读取，拒绝后不反复弹出申请。 */
export async function requestDesktopPermission(){
 if(!('Notification' in window))throw new Error('当前浏览器不支持桌面通知，请使用本机Edge或Chrome');
 if(Notification.permission==='default'){
  // 嵌入式浏览器可能不显示权限对话框；超时后允许重试，不能永久停在正在授权。
  let timer:ReturnType<typeof setTimeout>|undefined;
  try{await Promise.race([Notification.requestPermission(),new Promise<never>((_,reject)=>{timer=setTimeout(()=>reject(new Error('浏览器尚未完成授权；请在Edge或Chrome打开本机工作台后首次允许通知')),10000)})])}
  finally{if(timer)clearTimeout(timer)}
 }
 refreshNotificationPermission();
 return Notification.permission;
}

/** 提交一条已授权的本机通知；返回成功只表示浏览器接受，系统勿扰和输出设备仍需现场核对。 */
export function submitDesktopNotification(text:string,tag:string,onOpen?:()=>void){
 refreshNotificationPermission();
 if(state.permission!=='granted')return false;
 try{
  const notification=new Notification('灶安 · 监测事件',{body:text,tag});
  activeNotifications.add(notification);
  notification.onclose=()=>activeNotifications.delete(notification);
  notification.onclick=()=>{window.focus();onOpen?.();notification.close()};
  publish({notificationsSubmitted:state.notificationsSubmitted+1,error:''});return true;
 }catch{publish({error:'浏览器未能提交桌面通知，请检查站点及系统通知设置'});return false}
}
