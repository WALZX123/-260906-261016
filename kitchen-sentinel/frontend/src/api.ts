// 所有浏览器请求集中在这里，统一处理 Cookie、CSRF 和后端错误信息。
let csrf = '';
export const setCsrf = (value:string) => { csrf=value; };
export async function api<T>(path:string, init:RequestInit={}):Promise<T> {
  // CSRF 令牌只由登录接口返回，所有写请求统一经过这里，避免页面漏加校验头。
  const response=await fetch('/api/v1'+path,{...init,credentials:'include',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...init.headers}});
  if(!response.ok){
    // 代理或服务异常时可能返回 HTML，解析失败也必须转换成可读错误。
    const body=await response.json().catch(()=>({}));
    throw new Error(typeof body.detail==='string'?body.detail:response.status===422?'输入格式或数值范围不正确':`请求失败 (${response.status})`);
  }
  // 当前接口均返回 JSON；单独保留解析位置，便于将来兼容 204 无内容响应。
  return response.json() as Promise<T>;
}
export const post = <T>(path:string,data:unknown={}) => api<T>(path,{method:'POST',body:JSON.stringify(data)});

// 退出接口不经过登录态和 CSRF：用户可能停留在登录页，且退出动作只允许本机
// 前端携带专用标识调用，后端会先返回 202，再优雅停止 API 与模拟器。
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
