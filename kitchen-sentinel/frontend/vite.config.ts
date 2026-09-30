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
