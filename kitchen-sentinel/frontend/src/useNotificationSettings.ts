/** 文件职责：账号通知设置的读取、保存及运行层联动。
 * 主要功能：登录/重启恢复数据库偏好、保存本人修改、失败提示及注销时停止提示音。
 * 技术栈：React Hooks、REST、CSRF；关联auth通知接口、Settings、AlarmNotifier和通知运行层。
 * 编写/修改日期（日志对应）：2026-10-16。默认值在代码中定义，实际保存以服务器成功响应为准。 */
import {useCallback,useEffect,useRef,useState,useSyncExternalStore} from 'react';
import {api} from './api';
import {configureNotificationSound,notificationRuntime} from './notificationRuntime';

/** 两个个人提醒开关；与浏览器权限、设备蜂鸣器及业务写权限独立。 */
export interface NotificationPreferences{sound_enabled:boolean;desktop_enabled:boolean}
/** 设置组件与全局报警共用同一控制器，避免各处开关互相覆盖。 */
export interface NotificationSettingsController{
 preferences:NotificationPreferences;ready:boolean;saving:boolean;error:string;
 update:(key:keyof NotificationPreferences,value:boolean)=>Promise<void>;
 reload:()=>Promise<void>;
}
export const DEFAULT_NOTIFICATION_PREFERENCES:NotificationPreferences={sound_enabled:true,desktop_enabled:true};

/** 订阅音频和真实授权状态；系统设置与自检页同步呈现。 */
export function useNotificationRuntime(){return useSyncExternalStore(notificationRuntime.subscribe,notificationRuntime.getSnapshot)}

/** 以账号为边界读取服务器设置；迟到响应不能覆盖已注销或换号后的状态。 */
export function useNotificationSettings(username:string|null,notify:(message:string)=>void):NotificationSettingsController{
 const [preferences,setPreferences]=useState(DEFAULT_NOTIFICATION_PREFERENCES),[ready,setReady]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState('');
 const identity=useRef(username),busy=useRef(false);
 identity.current=username;
 const reload=useCallback(async()=>{
  if(!username)return;
  try{
   const value=await api<NotificationPreferences>('/auth/notification-preferences');
   if(identity.current!==username)return;
   setPreferences(value);setReady(true);setError('');
  }catch(e){if(identity.current===username){setError((e as Error).message);setReady(false)}}
 },[username]);
 useEffect(()=>{setReady(false);setError('');setSaving(false);busy.current=false;configureNotificationSound(false);if(username)void reload()},[username,reload]);
 useEffect(()=>{configureNotificationSound(ready&&preferences.sound_enabled)},[ready,preferences.sound_enabled]);

 /** 只在服务器确认写入后更新开关；串行保存，防止快速连续点击产生乱序覆盖。 */
 const update=async(key:keyof NotificationPreferences,value:boolean)=>{
  if(!username||!ready||busy.current)return;
  busy.current=true;setSaving(true);
  try{
   const result=await api<NotificationPreferences>('/auth/notification-preferences',{method:'PUT',body:JSON.stringify({...preferences,[key]:value})});
   if(identity.current===username){setPreferences(result);setError('');notify('通知设置已保存，下次登录自动读取')}
  }catch(e){if(identity.current===username){setError((e as Error).message);notify('通知设置保存失败，请重试')}}
  finally{if(identity.current===username){busy.current=false;setSaving(false)}}
 };
 return {preferences,ready,saving,error,update,reload};
}
