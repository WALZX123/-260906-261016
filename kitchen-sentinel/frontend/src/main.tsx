/**
 * 文件职责：浏览器应用挂载入口。
 * 主要功能：把根组件挂载到页面并载入全局样式。
 * 技术栈：React StrictMode、ReactDOM createRoot、TypeScript、CSS。
 * 模块联动：index.html 提供 root，App 组织业务页面，styles.css 提供布局和状态外观。
 * 编写/修改日期（日志对应）：2026-10-03。
 */
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
