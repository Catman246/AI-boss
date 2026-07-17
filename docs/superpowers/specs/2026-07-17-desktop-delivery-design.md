# 招聘助手桌面交付设计

## 目标

把现有本地招聘系统交付为 Windows 桌面程序。用户双击桌面“招聘助手”后，系统以独立桌面窗口打开，后台服务不显示终端，同时启动由 DrissionPage 控制的专用 Chrome。

## 用户流程

1. 启动桌面程序，程序在 `127.0.0.1:8765` 启动 FastAPI，并打开桌面 WebView2 窗口。
2. 程序启动专用 BOSS Chrome，并导航到 BOSS 沟通页。
3. 首次使用或登录失效时，BOSS 页面显示官方登录/验证流程，由用户人工完成。
4. 后续启动复用固定 Chrome 用户目录中的 Cookie 和本地存储；登录仍有效时直接进入沟通页。
5. 关闭桌面窗口时停止 FastAPI、调度线程并关闭该专用 Chrome；数据库和登录态保留。

## 架构

- `desktop.py` 是唯一桌面入口，负责单实例锁、用户目录准备、Uvicorn 线程、WebView2 窗口和退出清理。
- 现有 `create_app()` 继续提供全部 HTTP/API 功能，只增加可注入的运行数据目录和种子资源目录。
- `BossAdapter` 继续独占 BOSS 自动化，只增加公开的启动与关闭生命周期方法；浏览器端口保持 `9333`。
- 桌面壳使用 `pywebview 6.2.1` 的 Edge Chromium 渲染器，不重写现有 HTML/CSS/JavaScript。

## 文件与数据

- 程序文件：PyInstaller `onedir` 目录，由 Inno Setup 安装到用户程序目录。
- 用户数据：`%LOCALAPPDATA%\RecruitingConsole\data`。
- Kimi 配置：`%LOCALAPPDATA%\RecruitingConsole\.env`，安装包不包含私钥。
- WebView 数据：`%LOCALAPPDATA%\RecruitingConsole\WebView`。
- BOSS 登录态：`%LOCALAPPDATA%\DrissionPage\Chrome9333`，沿用现有专用配置目录。
- 日志：`%LOCALAPPDATA%\RecruitingConsole\logs\desktop.log`。

首次运行只在目标文件不存在时迁移当前项目的数据库、模型缓存和 `.env`，绝不覆盖已有用户数据。

## 安全与故障处理

- FastAPI 和 Chrome 调试端口只监听本机。
- 不读取、导出或复制 BOSS Cookie，不绕过验证码、风控和登录限制。
- 登录失效时保留官方登录页并暂停自动操作。
- 重复启动由单实例文件锁拦截。
- 后端、WebView2 或 Chrome 启动失败时显示 Windows 错误框，并把详细错误写入本地日志。

## 交付

- `dist\RecruitingAssistant\RecruitingAssistant.exe`：可直接运行的 onedir 成品。
- `release\招聘助手-安装包.exe`：正式安装包，创建桌面和开始菜单快捷方式。
- EXE、卸载项和快捷方式统一使用 `assets\app-icon.ico`。

## 验收

- 无终端窗口。
- 桌面窗口正确加载现有系统。
- 专用 Chrome 自动打开 BOSS；首次可人工登录，重启后复用登录态。
- 重复点击 EXE 不启动第二套服务。
- 关闭桌面窗口后 `8765` 端口释放，Chrome 配置目录和业务数据仍存在。
