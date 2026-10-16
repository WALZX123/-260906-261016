/** 文件职责：账号通知设置与浏览器实际状态展示。
 * 主要功能：保存提示音/桌面通知开关、一次性授权、显示已恢复或受浏览器限制的状态。
 * 技术栈：React、TypeScript、REST、Web API；关联系统设置与通知运行层，不操作现场执行器。
 * 编写/修改日期（日志对应）：2026-10-16。 */
import {useState} from 'react';
import {Panel,Badge} from './components';
import {useNotificationRuntime} from './useNotificationSettings';
import type {NotificationSettingsController} from './useNotificationSettings';
import {requestDesktopPermission} from './notificationRuntime';

/** 所有账号均可管理本人提醒，账号权限及现场保护不随通知开关改变。 */
export function NotificationSettings({settings,notify}:{settings:NotificationSettingsController;notify:(message:string)=>void}){
 const runtime=useNotificationRuntime(),[requesting,setRequesting]=useState(false);
 const {preferences,ready,saving,error}=settings;
 /** 权限已授予时不重复申请；首次授权和解除浏览器屏蔽仍由使用者明确操作。 */
 const authorize=async()=>{
  setRequesting(true);
  try{const result=await requestDesktopPermission();notify(result==='granted'?'桌面通知已授权，后续启动自动沿用':'浏览器尚未允许桌面通知，已保存的开关继续保留')}
  catch(e){notify((e as Error).message)}finally{setRequesting(false)}
 };
 const soundStatus=!ready?'正在读取':!preferences.sound_enabled?'已关闭':runtime.audio==='ready'?'已恢复':runtime.audio==='unsupported'?'浏览器不支持':'正常点击页面后自动就绪';
 const desktopStatus=!ready?'正在读取':!preferences.desktop_enabled?'已关闭':runtime.permission==='granted'?'已授权，自动恢复':runtime.permission==='denied'?'浏览器已阻止':runtime.permission==='unsupported'?'浏览器不支持':'首次使用需授权';
 return <Panel title="我的通知设置" extra={<Badge>{saving?'正在保存':ready?'按账号保存':'正在读取'}</Badge>}>
  <p>提示音与桌面通知默认开启。修改后保存到本机数据库，登录、刷新或重启系统都会读取；使用同一账号时无需反复设置。</p>
  <div className="notification-preferences">
   <label><input type="checkbox" checked={preferences.sound_enabled} disabled={!ready||saving} onChange={e=>void settings.update('sound_enabled',e.target.checked)}/><span><strong>页面提示音</strong><small>{soundStatus}</small></span></label>
   <label><input type="checkbox" checked={preferences.desktop_enabled} disabled={!ready||saving} onChange={e=>void settings.update('desktop_enabled',e.target.checked)}/><span><strong>桌面通知</strong><small>{desktopStatus}</small></span></label>
  </div>
  {ready&&preferences.desktop_enabled&&runtime.permission==='default'&&<button className="button secondary" disabled={requesting} onClick={()=>void authorize()}>首次授权桌面通知</button>}
  {preferences.desktop_enabled&&runtime.permission==='denied'&&<p className="muted">请在浏览器地址栏的站点权限中允许通知。系统会读取授权结果，不反复弹出申请。</p>}
  <p className="muted">登录、切页或其他正常点击会自动恢复浏览器允许的声音播放；首次通知授权由浏览器保存。页面关闭后的外部推送尚未接入。通知自检统一在“系统测试”中。</p>
  {error&&<p role="alert">设置读取或保存未完成：{error} <button className="text-button" onClick={()=>void settings.reload()}>重新读取</button></p>}
 </Panel>;
}
