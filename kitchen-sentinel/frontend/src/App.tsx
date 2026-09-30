// 应用壳负责登录恢复、导航、实时监控订阅和演示场景入口；具体页面保持独立。
import {useCallback,useEffect,useState} from 'react';
import {Activity,ArrowRight,Bell,BookOpen,ChevronRight,ClipboardList,Database,FlaskConical,LayoutDashboard,LogOut,Play,Power,Radio,Settings2,ShieldCheck,SlidersHorizontal,X} from 'lucide-react';
import {api,post,requestShutdown,setCsrf} from './api';
import {useMonitor} from './useMonitor';
import {Badge,labels,Modal,Notice} from './components';
import {Overview} from './pages/Overview';
import {Alarms} from './pages/Alarms';
import {Control} from './pages/Control';
import {History} from './pages/History';
import {Devices} from './pages/Devices';
import {Settings} from './pages/Settings';
import {Audit} from './pages/Audit';
import type {User,Page} from './types';
const nav=[{id:'overview',name:'监控总览',icon:LayoutDashboard},{id:'devices',name:'设备管理',icon:Radio},{id:'alarms',name:'报警中心',icon:Bell},{id:'control',name:'联动控制',icon:SlidersHorizontal},{id:'history',name:'历史数据',icon:Database},{id:'settings',name:'系统设置',icon:Settings2},{id:'audit',name:'操作审计',icon:ClipboardList}] as const;
const descriptions:Record<Page,string>={overview:'掌握厨房运行状态，及时发现异常',devices:'管理现场节点，查看连接与采样状态',alarms:'从异常触发到人工处理，保留完整记录',control:'下发保护指令，追踪每一次执行反馈',history:'回看监测曲线，追溯事件发生过程',settings:'管理报警策略、账号权限与系统配置',audit:'追踪关键操作，核对系统行为'};
const scenarios=[['normal','正常监测','稳定的基线数据，恢复异常场景'],['gas','燃气持续升高','模拟持续泄漏趋势，验证阈值报警与关阀'],['fire','火灾信号','烟雾与温度持续上升，随后检出火焰'],['spike','短时尖峰','验证持续时间判定对瞬时干扰的抑制'],['sensor_fault','传感器故障','发送无效采样，验证数据质量与故障告警'],['offline','上报中断','暂停上报 25 秒，验证离线检测与恢复'],['command_timeout','执行超时','暂停执行命令，验证超时记录']];

function ExitOverlay(){
 // 请求已经送达后锁定界面，防止用户连续点击造成重复请求。
 return <div className="shutdown-overlay" role="status" aria-live="polite"><div><Power size={28}/><strong>正在安全退出系统</strong><span>正在停止 API 和设备模拟器，请稍候…</span></div></div>;
}

function Login({onLogin,onExit,shuttingDown}:{onLogin:(u:User)=>void;onExit:()=>void;shuttingDown:boolean}){
 // 登录页不保存密码；成功后只把后端返回的会话信息交给上层状态管理。
 const [name,setName]=useState('admin'),[password,setPassword]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 return <div className="login-page"><div className="login-intro"><div className="brand"><ShieldCheck/><span>灶安 <small>KITCHEN SENTINEL</small></span></div><div><div className="eyebrow">OBSERVE · RESPOND · TRACE</div><h1>看见风险，<br/>守住厨房的每一刻。</h1><p>连接数据、报警与保护动作。<br/>一套可追溯、可扩展的厨房安全监测工作台。</p><div className="login-pills"><span>实时监测</span><span>联动控制</span><span>事件追溯</span></div></div><small>本机部署 · 教学仿真环境 · v1.0</small></div><div className="login-form"><form onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');try{onLogin(await post<User>('/auth/login',{username:name,password}))}catch(err){setError((err as Error).message)}finally{setBusy(false)}}}><span className="eyebrow">WELCOME BACK</span><h2>登录监测工作台</h2><p>使用本机初始化时生成的账号登录</p><label>用户名<input autoComplete="username" value={name} onChange={e=>setName(e.target.value)} required/></label><label>密码<input autoComplete="current-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></label>{error&&<div className="form-error" role="alert">{error}</div>}<button className="button" disabled={busy}>{busy?'正在登录':'进入工作台'}<ArrowRight size={18}/></button><small>登录信息保存在项目 .runtime/access.txt 文件中。<br/>当前数据来自设备模拟器，真实硬件尚未接入。</small></form><button type="button" className="login-exit" onClick={onExit} disabled={shuttingDown}><Power size={16}/>退出系统<span>Ctrl + Shift + Q</span></button></div>{shuttingDown&&<ExitOverlay/>}</div>;
}

export default function App(){
 // 首次加载先恢复 Cookie 会话，再决定显示登录页还是工作台。
 const [user,setUser]=useState<User|null>(null),[checking,setChecking]=useState(true),[page,setPage]=useState<Page>('overview'),[demo,setDemo]=useState(false),[help,setHelp]=useState(false),[toast,setToast]=useState(''),[busy,setBusy]=useState(false),[shuttingDown,setShuttingDown]=useState(false);
 const notify=useCallback((message:string)=>setToast(message),[]);
 const {snapshot:data,samples,connected,error,refresh}=useMonitor(!!user);
 const login=useCallback((u:User)=>{setCsrf(u.csrf_token);setUser(u)},[]);
 const exitSystem=useCallback(async()=>{
  if(shuttingDown)return;
  if(!window.confirm('将安全停止后端、设备模拟器和当前页面。不会删除数据库或修改业务数据。确认退出吗？'))return;
  setShuttingDown(true);
  try{await requestShutdown()}catch(err){setShuttingDown(false);setToast((err as Error).message||'退出请求未发送，请使用启动窗口中的 Ctrl+C')}
 },[shuttingDown]);
 useEffect(()=>{api<User>('/auth/me').then(login).catch(()=>{}).finally(()=>setChecking(false))},[login]);
 useEffect(()=>{if(!toast)return;const timer=setTimeout(()=>setToast(''),6000);return()=>clearTimeout(timer)},[toast]);
 useEffect(()=>{
  const handleShortcut=(event:KeyboardEvent)=>{
   if(event.ctrlKey&&event.shiftKey&&event.key.toLowerCase()==='q'){event.preventDefault();void exitSystem()}
  };
  window.addEventListener('keydown',handleShortcut);
  return()=>window.removeEventListener('keydown',handleShortcut);
 },[exitSystem]);
 if(checking)return <div className="loading"><ShieldCheck size={36}/><p>正在连接工作台…</p></div>;
 if(!user)return <Login onLogin={login} onExit={()=>void exitSystem()} shuttingDown={shuttingDown}/>;
 const activeNav=nav.find(n=>n.id===page)!;
 const logout=async()=>{await post('/auth/logout');setUser(null);setCsrf('')};
 // 场景设置只改变模拟设备的输入，不绕过真实的设备上报和报警链路。
 const switchScenario=async(scenario:string)=>{if(!data?.devices[0])return;setBusy(true);try{await post(`/devices/${data.devices[0].id}/scenario`,{scenario});notify('场景已选择，模拟器将在下一轮同步后应用');await refresh();setDemo(false)}catch(e){notify((e as Error).message)}finally{setBusy(false)}};
 return <div className="app-shell"><aside className="sidebar"><div className="brand"><ShieldCheck size={33}/><span>灶安<small>KITCHEN SENTINEL</small></span></div><div className="workspace-label">厨房安全监测平台 <Badge>本地</Badge></div><nav>{nav.filter(n=>n.id!=='audit'||user.role==='admin').map(n=><button key={n.id} onClick={()=>setPage(n.id)} className={page===n.id?'active':''}><n.icon size={19}/><span>{n.name}</span>{n.id==='alarms'&&!!data?.stats.active_alarms&&<b>{data.stats.active_alarms}</b>}</button>)}</nav><div className="sidebar-bottom"><div className="environment"><span className="dot"/><span>教学仿真环境<small>数据来源清晰 · 全程留痕</small></span></div><button className="sidebar-help" onClick={()=>setHelp(true)}><BookOpen size={17}/>演示与使用说明<ChevronRight size={15}/></button><button className="sidebar-exit" onClick={()=>void exitSystem()} disabled={shuttingDown}><Power size={16}/>退出系统<small>Ctrl + Shift + Q</small></button><div className="user"><div className="avatar">{user.username[0].toUpperCase()}</div><div><strong>{user.username}</strong><small>{labels[user.role]}</small></div><button aria-label="退出登录" onClick={()=>logout().catch(e=>notify(e.message))}><LogOut size={17}/></button></div></div></aside><main><header><div className="breadcrumb">工作台 <ChevronRight size={13}/><span>{activeNav.name}</span></div><div className="header-right"><span className={'connection '+(connected?'':'disconnected')}><span className="dot"/>{connected?'实时连接正常':'正在重连'}</span><span className="header-divider"/><span>{new Date().toLocaleDateString('zh-CN',{year:'numeric',month:'long',day:'numeric'})}</span></div></header><div className="content"><div className="page-heading"><div><div className="eyebrow">{page.toUpperCase()}</div><h1>{activeNav.name}</h1><p>{descriptions[page]}</p></div><div className="button-row"><button className="button secondary" onClick={()=>setHelp(true)}><BookOpen size={16}/>使用说明</button><button className="button" disabled={user.role==='viewer'} onClick={()=>setDemo(true)}><FlaskConical size={17}/>演示场景</button></div></div>{error&&<Notice warn>{error}</Notice>}{!data?<div className="loading"><Activity/><p>正在加载设备与监测数据…</p><button className="button secondary" onClick={()=>void refresh()}>重新连接</button></div>:<>{page==='overview'&&<Overview data={data} samples={samples} navigate={setPage}/>} {page==='devices'&&<Devices data={data}/>} {page==='alarms'&&<Alarms data={data} user={user} refresh={refresh} notify={notify}/>} {page==='control'&&<Control data={data} user={user} refresh={refresh} notify={notify}/>} {page==='history'&&<History data={data} notify={notify}/>} {page==='settings'&&<Settings data={data} user={user} refresh={refresh} notify={notify}/>} {page==='audit'&&<Audit notify={notify}/>}</>}<footer>Kitchen Sentinel · 厨房安全监测平台<span>现场判断 / 数据记录 / 辅助分析</span></footer></div></main>{toast&&<div className="toast" role="status">{toast}<button aria-label="关闭提示" onClick={()=>setToast('')}><X size={15}/></button></div>}{demo&&<Modal title="演示场景" onClose={()=>setDemo(false)}><Notice>场景通过设备模拟器产生数据，进入与真实设备相同的接入、存储和展示流程。</Notice><div className="scenario-list">{scenarios.map(([id,title,description])=><button key={id} disabled={busy} onClick={()=>switchScenario(id)} className={data?.devices[0]?.scenario===id?'selected':''}><div><strong>{title}</strong><p>{description}</p></div>{data?.devices[0]?.scenario===id?<Badge>当前</Badge>:<Play size={18}/>}</button>)}</div></Modal>}{help&&<Modal title="演示与使用说明" onClose={()=>setHelp(false)}><ol className="help-list"><li><strong>从监控总览开始</strong><p>确认设备在线，观察实时数值、曲线和现场状态。所有数据均标记为教学仿真。</p></li><li><strong>触发燃气持续升高</strong><p>打开演示场景，选择燃气持续升高。约十秒后观察报警与模拟关阀。</p></li><li><strong>追溯报警过程</strong><p>进入报警中心，查看事件时间线，填写处理说明并确认报警，再生成规则摘要。</p></li><li><strong>验证控制反馈</strong><p>在联动控制中发送关阀或自检命令，区分下发状态与设备执行结果。</p></li><li><strong>查询历史与异常恢复</strong><p>查询历史数据并导出 CSV；切回正常场景，观察报警恢复。阀门不会自动重新开启。</p></li><li><strong>展示故障处理</strong><p>测试传感器故障、上报中断及命令超时，查看报警、连接状态与审计记录。</p></li></ol><Notice>当前范围：本地 Web + Python 后端 + MySQL + 模拟器。手机端、云部署、真实硬件及实物标定属于后续阶段。</Notice></Modal>}{shuttingDown&&<ExitOverlay/>}</div>;
}
