/**
 * 文件职责：浏览器与后端的通信适配。
 * 主要功能：统一 Cookie 和 CSRF、解析 API 错误、封装 POST 及本机退出请求。
 * 技术栈：TypeScript 泛型、Fetch API、JSON、Cookie/CSRF。
 * 模块联动：App 和全部页面经本模块访问 FastAPI；退出调用独立本机接口，不能作为设备控制。
 * 编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-09-30；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
 */
// 所有浏览器请求集中在这里，统一处理 Cookie、CSRF 和后端错误信息。
let csrf = '';
/** 在内存中更新写请求令牌，登录成功时设置，退出登录时清空；不把密码存入浏览器状态持久层。
 * 编写/修改日期（日志对应）：2026-09-30。 */
export const setCsrf = (value:string) => { csrf=value; };
/** 按路径发起带 Cookie 和 CSRF 的请求，统一解析后端错误，返回泛型约定的 JSON 数据。
 * 编写/修改日期（日志对应）：2026-09-30。 */
export async function api<T>(path:string, init:RequestInit={}):Promise<T> {
  // CSRF 令牌只由登录接口返回，所有写请求统一经过这里，避免页面漏加校验头。
  const response=await fetch('/api/v1'+path,{signal:AbortSignal.timeout(35000),cache:'no-store',...init,credentials:'include',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...init.headers}});
  if(!response.ok){
    if(response.status===405)window.dispatchEvent(new Event('ks-service-mismatch'));
    if(response.status===401)window.dispatchEvent(new Event('ks-session-expired'));
    // 代理或服务异常时可能返回 HTML，解析失败也必须转换成可读错误。
    const body=await response.json().catch(()=>({}));
    const messages:Record<number,string>={401:'登录已过期，请重新登录',403:'当前账号无此操作权限或会话校验失效，请重新登录',404:'接口或记录不存在，请刷新页面检查服务版本',405:'当前服务不支持此操作，请更新服务后刷新页面',422:'输入格式或数值范围不正确'};
    throw new Error(response.status===405?messages[405]:typeof body.detail==='string'?body.detail:messages[response.status]||`请求失败 (${response.status})`);
  }
  // 当前接口均返回 JSON；单独保留解析位置，便于将来兼容 204 无内容响应。
  return response.json() as Promise<T>;
}
/** 把请求体编码为 JSON 并复用 api 的认证和错误处理，返回相应接口结果。
 * 编写/修改日期（日志对应）：2026-09-30。 */
export const post = <T>(path:string,data:unknown={}) => api<T>(path,{method:'POST',body:JSON.stringify(data)});

// 退出接口不经过登录态和 CSRF：用户可能停留在登录页，且退出动作只允许本机
// 前端携带专用标识调用，后端会先返回 202，再优雅停止 API 与模拟器。
/** 向本机退出接口发送专用标识，交由后端和总入口停止本次系统；失败时保留可读错误。
 * 编写/修改日期（日志对应）：2026-09-30。 */
export async function requestShutdown():Promise<void> {
  const response=await fetch('/api/shutdown',{
    method:'POST',
    credentials:'same-origin',
    headers:{'X-Local-Exit':'kitchen-sentinel'},
  });
  if(!response.ok){
    const body=await response.json().catch(()=>({}));
    throw new Error(typeof body.detail==='string'?body.detail:`退出请求失败 (${response.status})`);
  }
}
