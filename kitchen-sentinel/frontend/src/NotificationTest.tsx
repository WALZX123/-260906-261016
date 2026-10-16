/** 文件职责：系统测试中的浏览器提醒自检。
 * 功能：验证已保存的提示音与桌面通知设置，呈现浏览器提交计数，不生成现场报警。
 * 技术栈：React、Web Audio、Notification；关联通知运行层和个人设置。
 * 编写/修改日期（日志对应）：2026-10-16。 */
import {Panel} from './components';
import {playAlertTone,submitDesktopNotification} from './notificationRuntime';
import {useNotificationRuntime} from './useNotificationSettings';
import type {NotificationSettingsController} from './useNotificationSettings';
/** 自检受个人开关与真实授权约束；提交成功不等于扬声器可闻或系统横幅可见。 */
export function NotificationTest({settings,notify}:{settings:NotificationSettingsController;notify:(message:string)=>void}){
 const runtime=useNotificationRuntime();
 const audioLabel={waiting:'等待页面交互',ready:'已就绪',unsupported:'浏览器不支持',error:'未就绪'}[runtime.audio];
 const permissionLabel={default:'首次待授权',granted:'已授权',denied:'浏览器已阻止',unsupported:'浏览器不支持'}[runtime.permission];
 return <Panel title="提示音与桌面通知自检"><p>提醒偏好由账号自动恢复。首次桌面授权在“系统设置”完成；自检不会操作硬件或更改报警记录。</p><div className="button-row">
  <button className="button secondary" disabled={!settings.ready||!settings.preferences.sound_enabled} onClick={()=>notify(playAlertTone()?'浏览器已播放测试音，请核对扬声器':'音频尚待浏览器允许，请正常点击页面后再试')}>测试页面提示音</button>
  <button className="button secondary" disabled={!settings.ready||!settings.preferences.desktop_enabled||runtime.permission!=='granted'} onClick={()=>notify(submitDesktopNotification('系统测试：桌面通知通道检查，不是现场报警','notification-self-test')?'测试通知已提交，请核对系统横幅':'通知提交未完成，请检查系统设置')}>测试桌面通知</button></div>
  <p className="muted">音频状态：{audioLabel} · 桌面权限：{permissionLabel} · 本次页面音频输出 {runtime.tonesPlayed} 次 · 桌面通知提交 {runtime.notificationsSubmitted} 次。操作系统勿扰、静音及输出设备请现场核对。</p></Panel>;
}
