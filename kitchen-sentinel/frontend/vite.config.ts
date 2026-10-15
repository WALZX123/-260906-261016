/**
 * 文件职责：前端开发与构建配置。
 * 主要功能：启用 React 转换、代理 API 和 WebSocket、拆分图表与图标依赖。
 * 技术栈：Vite、React 插件、Rollup manualChunks、TypeScript。
 * 模块联动：开发代理到 FastAPI，生产输出 dist 由 backend.main 托管，不独立承担业务接口。
 * 编写/修改日期（日志对应）：2026-09-11。
 */
// 开发服务器只代理 API；生产构建由 FastAPI 直接托管 dist 目录。
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins:[react()],
  server:{proxy:{'/api':{target:'http://127.0.0.1:8000',ws:true},'/docs':'http://127.0.0.1:8000'}},
  build:{
    // 将稳定的第三方依赖拆开，首次加载和后续缓存更新都更可控。
    rollupOptions:{output:{manualChunks:{charts:['recharts'],icons:['lucide-react']}}},
  },
});
