/**
 * 文件职责：工作台登录、导航与实时监控入口。
 * 主要功能：恢复会话、展示实物监控及全站报警通知，独立进入系统测试并处理本机退出。
 * 技术栈：React Hooks、TypeScript、REST、WebSocket、Lucide 图标。
 * 模块联动：useMonitor 订阅实物；AlarmNotifier 通知险情；pages 按职责展示业务，SystemTest 集中测试。
 * 编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-10-03、2026-10-09、2026-10-13。
 */
import {useCallback,useEffect,useState} from 'react';
import {Activity,ArrowRight,Bell,BookOpen,ChevronRight,ClipboardList,Database,FlaskConical,LayoutDashboard,LogOut,Power,Radio,RefreshCw,Settings2,ShieldCheck,SlidersHorizontal,X} from 'lucide-react';
import {api,post,requestShutdown,setCsrf} from './api';
import {useMonitor} from './useMonitor';
import {Badge,labels,Modal,Notice} from './components';
import {AlarmNotifier} from './AlarmNotifier';
import {Overview} from './pages/Overview';
import {Alarms} from './pages/Alarms';
import {Control} from './pages/Control';
import {History} from './pages/History';
import {Devices} from './pages/Devices';
import {Settings} from './pages/Settings';
import {Audit} from './pages/Audit';
import {Activation} from './pages/Activation';
import {SystemTest} from './pages/SystemTest';
import type {User,Page} from './types';
const nav=[{id:'activation',name:'设备启用',icon:Power},{id:'overview',name:'监控总览',icon:LayoutDashboard},{id:'devices',name:'设备管理',icon:Radio},{id:'alarms',name:'报警中心',icon:Bell},{id:'control',name:'联动控制',icon:SlidersHorizontal},{id:'history',name:'历史数据',icon:Database},{id:'testing',name:'系统测试',icon:FlaskConical},{id:'settings',name:'系统设置',icon:Settings2},{id:'audit',name:'操作审计',icon:ClipboardList}] as const;
const descriptions:Record<Page,string>={activation:'显式开启现场采样，检查运行与无线连接状态',overview:'实时掌握厨房状态，及时发现并处置异常',devices:'查看现场节点连接、采样与保护输出',alarms:'异常自动留档，恢复后仍需人工确认',control:'下发保护指令，追踪设备执行反馈',history:'查询监测曲线，追溯事件发生过程',testing:'集中验证软件流程与硬件功能',settings:'管理报警策略、账号权限与系统配置',audit:'追踪关键操作，核对系统行为'};

/** 显示本机退出进度，阻止重复提交。
 * 编写/修改日期（日志对应）：2026-10-03。 */
function ExitOverlay(){return <div className="shutdown-overlay" role="status"><div><Power size={28}/><strong>正在安全退出系统</strong><span>正在停止服务与数据采集，请稍候…</span></div></div>}

/** 管理登录表单，密码只提交到本机认证接口，不持久化到浏览器。
 * 编写/修改日期（日志对应）：2026-09-30。 */
function Login({onLogin,onExit,shuttingDown}:{onLogin:(u:User)=>void;onExit:()=>void;shuttingDown:boolean}){
 const [name,setName]=useState('admin'),[password,setPassword]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 return <div className="login-page"><div className="login-intro"><div className="brand"><ShieldCheck/><span>灶安 <small>KITCHEN SENTINEL</small></span></div><div><div className="eyebrow">OBSERVE · RESPOND · TRACE</div><h1>看见风险，<br/>守住厨房的每一刻。</h1><p>连接现场数据、自动保护与人工处置。<br/>一套可追溯的厨房安全监测工作台。</p><div className="login-pills"><span>实时监测</span><span>自动保护</span><span>异常留档</span></div></div><small>本机部署 · 厨房安全监测平台</small></div><div className="login-form"><form onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');try{onLogin(await post<User>('/auth/login',{username:name,password}))}catch(err){setError((err as Error).message)}finally{setBusy(false)}}}><span className="eyebrow">WELCOME BACK</span><h2>登录监测工作台</h2><p>使用项目初始化的账号登录</p><label>用户名<input autoComplete="username" value={name} onChange={e=>setName(e.target.value)} required/></label><label>密码<input autoComplete="current-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></label>{error&&<div className="form-error" role="alert">{error}</div>}<button className="button" disabled={busy}>{busy?'正在登录':'进入工作台'}<ArrowRight size={18}/></button><small>账号信息见项目的本机访问说明。</small></form><button type="button" className="login-exit" onClick={onExit} disabled={shuttingDown}><Power size={16}/>退出系统<span>Ctrl + Shift + Q</span></button></div>{shuttingDown&&<ExitOverlay/>}</div>;
}

/** 统一组织正式实物页面与系统测试入口；全站通知在切换业务页面时持续工作。
 * 编写/修改日期（日志对应）：2026-10-03、2026-10-13。 */
export default function App(){
 const [user,setUser]=useState<User|null>(null),[checking,setChecking]=useState(true),[page,setPage]=useState<Page>('activation');
 const [serviceVersion,setServiceVersion]=useState(''),[mismatch,setMismatch]=useState(false);
 const [help,setHelp]=useState(false),[toast,setToast]=useState(''),[shuttingDown,setShuttingDown]=useState(false);
 const {snapshot:data,samples,connected,error,refresh,updatedAt}=useMonitor(!!user);
 /** 日志对应：2026-10-15。核对页面和运行服务能力，避免旧服务/旧标签页把操作误报为权限问题。 */
 useEffect(()=>{const check=()=>{void fetch('/api/health',{cache:'no-store'}).then(r=>r.json()).then(v=>{setServiceVersion(v.version||'未知');setMismatch(v.version!=='1.2.0'||!v.capabilities?.includes('activation'))}).catch(()=>{})};const mismatchEvent=()=>setMismatch(true);check();const timer=setInterval(check,30000);window.addEventListener('ks-service-mismatch',mismatchEvent);return()=>{clearInterval(timer);window.removeEventListener('ks-service-mismatch',mismatchEvent)}},[]);
 /** 保存会话和写请求校验令牌，开启监控订阅。
  * 编写/修改日期（日志对应）：2026-09-30。 */
 const login=useCallback((u:User)=>{setCsrf(u.csrf_token);setUser(u)},[]);
 /** 更新临时操作反馈，不改变报警的确认和处置状态。
  * 编写/修改日期（日志对应）：2026-10-03。 */
 const notify=useCallback((message:string)=>setToast(message),[]);
 /** 本机退出由总入口统一回收进程，用户确认后防止重复提交。
  * 编写/修改日期（日志对应）：2026-10-01。 */
 const exitSystem=useCallback(async()=>{
  if(shuttingDown||!window.confirm('确认退出系统并停止本机服务与采集？异常和历史记录将保留。'))return;
  setShuttingDown(true);
  try{await requestShutdown()}catch(err){setShuttingDown(false);notify((err as Error).message)}
 },[shuttingDown,notify]);
 /** 初次恢复 Cookie 会话，完成后显示登录或工作台。
  * 编写/修改日期（日志对应）：2026-09-30。 */
 useEffect(()=>{api<User>('/auth/me').then(login).catch(()=>{}).finally(()=>setChecking(false))},[login]);
 /** 会话过期时立即结束订阅并回到登录，保留服务端异常和控制记录。
  * 编写/修改日期（日志对应）：2026-10-12。 */
 useEffect(()=>{const expire=()=>{setUser(null);setCsrf('')};window.addEventListener('ks-session-expired',expire);return()=>window.removeEventListener('ks-session-expired',expire)},[]);
 /** 短反馈显示六秒；持续险情由独立通知条保存，避免被短提示覆盖。
  * 编写/修改日期（日志对应）：2026-10-03。 */
 useEffect(()=>{if(!toast)return;const timer=setTimeout(()=>setToast(''),6000);return()=>clearTimeout(timer)},[toast]);
 /** 切页后回到顶部并更新标题，避免继承测试长页的滚动位置而错过业务页入口。
  * 编写/修改日期（日志对应）：2026-10-13。 */
 useEffect(()=>{window.scrollTo(0,0);document.title=(nav.find(item=>item.id===page)?.name||'灶安')+' · Kitchen Sentinel'},[page]);
 /** 注册退出快捷键并在卸载时移除。
  * 编写/修改日期（日志对应）：2026-10-01。 */
 useEffect(()=>{const handle=(event:KeyboardEvent)=>{if(event.ctrlKey&&event.shiftKey&&event.key.toLowerCase()==='q'){event.preventDefault();void exitSystem()}};window.addEventListener('keydown',handle);return()=>window.removeEventListener('keydown',handle)},[exitSystem]);
 /** 服务端确认注销后清除前端令牌和用户资料。
  * 编写/修改日期（日志对应）：2026-09-30。 */
 const logout=async()=>{await post('/auth/logout');setUser(null);setCsrf('')};
 if(checking)return <div className="loading"><ShieldCheck size={36}/><p>正在连接工作台…</p></div>;
 if(!user)return <Login onLogin={login} onExit={()=>void exitSystem()} shuttingDown={shuttingDown}/>;
 const activeNav=nav.find(n=>n.id===page)!;
 return <div className="app-shell">
  <aside className="sidebar"><div className="brand"><ShieldCheck size={33}/><span>灶安<small>KITCHEN SENTINEL</small></span></div><div className="workspace-label">厨房安全监测平台 <Badge>本地</Badge></div>
   <nav>{nav.filter(n=>n.id!=='audit'||user.role==='admin').map(n=><button key={n.id} onClick={()=>setPage(n.id)} className={page===n.id?'active':''}><n.icon size={19}/><span>{n.name}</span>{n.id==='alarms'&&!!data?.stats.unacknowledged_alarms&&<b>{data.stats.unacknowledged_alarms}</b>}</button>)}</nav>
   <div className="sidebar-bottom"><div className="environment"><span className={'dot '+(!connected?'gray':'')}/><span>现场设备监控<small>自动保护 · 人工确认 · 全程留痕</small></span></div><button className="sidebar-help" onClick={()=>setHelp(true)}><BookOpen size={17}/>使用说明<ChevronRight size={15}/></button><button className="sidebar-exit" onClick={()=>void exitSystem()} disabled={shuttingDown}><Power size={16}/>退出系统<small>Ctrl + Shift + Q</small></button><div className="user"><div className="avatar">{user.username[0].toUpperCase()}</div><div><strong>{user.username}</strong><small>{labels[user.role]}</small></div><button aria-label="退出登录" onClick={()=>void logout().catch(e=>notify(e.message))}><LogOut size={17}/></button></div></div>
  </aside>
  <main><header><div className="breadcrumb">工作台 <ChevronRight size={13}/><span>{activeNav.name}</span></div><div className="header-right"><span className={'connection '+(connected?'':'disconnected')}><span className="dot"/>{connected?'实时推送正常':'实时重连 · 查询兜底'}</span><span className="header-divider"/><span>更新于 {updatedAt?new Date(updatedAt).toLocaleTimeString('zh-CN',{hour12:false}):'等待连接'}</span></div></header>
   <div className="content"><div className="page-heading"><div><div className="eyebrow">{page.toUpperCase()}</div><h1>{activeNav.name}</h1><p>{descriptions[page]}</p></div><div className="button-row"><button className="button secondary" onClick={()=>setHelp(true)}><BookOpen size={16}/>使用说明</button><button className="button secondary" onClick={()=>void refresh()}><RefreshCw size={16}/>立即刷新</button></div></div>
   {mismatch&&<Notice warn>页面与运行服务版本不匹配（当前服务 {serviceVersion}）。<button className="button secondary" onClick={()=>window.location.assign('http://127.0.0.1:8000/?reload='+Date.now())}>重新载入当前服务</button></Notice>}
   {error&&<Notice warn>{error}</Notice>}
   {!data?<div className="loading"><Activity/><p>正在加载设备与监测数据…</p><button className="button secondary" onClick={()=>void refresh()}>重新连接</button></div>:<>
    {page!=='activation'&&data.devices.some(d=>d.source==='hardware'&&d.latest.monitoring_enabled===false)&&<Notice>现场设备待机，硬件采样尚未开启。<button className="button secondary" onClick={()=>setPage('activation')}>前往设备启用</button></Notice>}
    <AlarmNotifier data={data} openAlarms={()=>setPage('alarms')}/>
    {page==='activation'&&<Activation data={data} user={user} refresh={refresh} notify={notify}/>}
    {page==='overview'&&<Overview data={data} samples={samples} navigate={setPage}/>}
    {page==='devices'&&<Devices data={data}/>}
    {page==='alarms'&&<Alarms data={data} user={user} refresh={refresh} notify={notify}/>}
    {page==='control'&&<Control data={data} user={user} refresh={refresh} notify={notify}/>}
    {page==='history'&&<History data={data} notify={notify}/>}
    {page==='testing'&&<SystemTest hardware={data} user={user} refresh={refresh} notify={notify}/>}
    {page==='settings'&&<Settings data={data} user={user} refresh={refresh} notify={notify}/>}
    {page==='audit'&&<Audit notify={notify}/>}
   </>}
   <footer>Kitchen Sentinel · 厨房安全监测平台 · 服务 {serviceVersion}<span>现场判断 / 数据记录 / 辅助分析</span></footer></div>
  </main>
  {toast&&<div className="toast" role="status">{toast}<button aria-label="关闭提示" onClick={()=>setToast('')}><X size={15}/></button></div>}
  {help&&<Modal title="使用说明" onClose={()=>setHelp(false)}><ol className="help-list"><li><strong>实时监控</strong><p>设备和报警自动刷新。请区分浏览器推送状态与现场设备在线状态；离线时读数是最后一次上报。</p></li><li><strong>异常处置</strong><p>能力范围内按策略自动关阀、报警和排风；火灾停普通风扇并转人工，超限、超时或执行失败同样升级。</p></li><li><strong>报警留档</strong><p>全部异常保留记录，自动恢复后仍需人工确认。现场发现执行异常，可填写说明并转人工。</p></li><li><strong>通知方式</strong><p>页面通知始终显示；提示音和桌面通知需点击开启。请保持浏览器页面运行。</p></li><li><strong>测试与维护</strong><p>软件场景和硬件分项测试统一进入系统测试。相对指标和估算温度需继续标定，输出回执不能代替机械动作验收。</p></li></ol></Modal>}
  {shuttingDown&&<ExitOverlay/>}
 </div>;
}
