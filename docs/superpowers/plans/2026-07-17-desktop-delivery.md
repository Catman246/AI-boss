# 招聘助手桌面交付 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成无终端的 Windows 桌面程序和安装包，并可靠管理现有 FastAPI 与专用 BOSS Chrome 的完整生命周期。

**Architecture:** `desktop.py` 在主进程中运行 pywebview，在后台线程运行 Uvicorn，并向 `create_app()` 注入用户数据目录和一个 `BossAdapter`。PyInstaller 生成 onedir，Inno Setup 仅负责安装程序文件和快捷方式，用户数据始终位于 LocalAppData。

**Tech Stack:** Python 3.13、pywebview 6.2.1、WebView2、Uvicorn、DrissionPage 4.1.1.4、PyInstaller 6.21.0、Inno Setup 6。

## Global Constraints

- 桌面主界面必须是独立 EXE 窗口，BOSS 必须是独立可见 Chrome。
- 不显示终端，不使用 Electron，不生成单文件自解压包。
- BOSS 登录和安全验证必须由用户在官方页面人工完成。
- 不覆盖既有数据库、Kimi 配置、模型缓存或 Chrome 登录态。
- 所有监听地址必须是 `127.0.0.1`。

---

### Task 1: 可迁移运行数据目录

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces: `create_app(..., data_dir: Path | None = None, seed_dir: Path | None = None) -> FastAPI`

- [ ] 写失败测试，断言注入的数据目录创建三个数据库并使用注入的种子目录。
- [ ] 运行 `python -m unittest tests.test_api -v`，确认因参数不存在而失败。
- [ ] 在 `create_app()` 内用局部 `runtime_data` 和 `resources` 替换固定 `DATA_DIR`。
- [ ] 重跑测试并确认通过。

### Task 2: BOSS 浏览器生命周期

**Files:**
- Modify: `app/boss.py`
- Test: `tests/test_boss.py`

**Interfaces:**
- Produces: `BossAdapter.launch() -> dict[str, Any]`
- Produces: `BossAdapter.close() -> None`

- [ ] 写失败测试，断言 `launch()` 打开并激活沟通页，`close()` 退出受控浏览器并清空缓存引用。
- [ ] 运行 `python -m unittest tests.test_boss -v`，确认新方法缺失。
- [ ] 使用现有 `_managed_page()` 和 `_connect()` 实现两个最小生命周期方法。
- [ ] 重跑测试并确认通过。

### Task 3: 桌面入口与退出清理

**Files:**
- Create: `desktop.py`
- Create: `tests/test_desktop.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `app_home(environ: Mapping[str, str]) -> Path`
- Produces: `prepare_user_data(home: Path, resources: Path, project_root: Path) -> None`
- Produces: `DesktopRuntime.start_server()`, `DesktopRuntime.stop()`
- Produces: `main() -> int`

- [ ] 写失败测试，覆盖 LocalAppData 路径、只复制缺失文件、模型目录迁移和 Uvicorn 退出标志。
- [ ] 运行 `python -m unittest tests.test_desktop -v`，确认模块不存在。
- [ ] 实现文件锁、日志、数据准备、后台 Uvicorn、pywebview 窗口和 `finally` 清理。
- [ ] 重跑桌面测试和完整测试套件。

### Task 4: onedir 与安装器

**Files:**
- Create: `desktop.spec`
- Create: `installer.iss`
- Create: `build-desktop.ps1`
- Create: `requirements-build.txt`

**Interfaces:**
- Produces: `dist\RecruitingAssistant\RecruitingAssistant.exe`
- Produces: `release\招聘助手-安装包.exe`

- [ ] 固定 PyInstaller 构建依赖并配置动态导入、静态资源、模型缓存和应用图标。
- [ ] 构建 onedir，确认 EXE 版本无控制台且包含 `app/static` 与模型资源。
- [ ] 配置 Inno Setup 为当前用户安装、创建桌面/开始菜单快捷方式并保留 LocalAppData。
- [ ] 编译安装包并检查输出文件存在且非空。

### Task 5: 真实成品验收

**Files:**
- Verify only: `dist\RecruitingAssistant\RecruitingAssistant.exe`
- Verify only: `%LOCALAPPDATA%\RecruitingConsole`

**Interfaces:**
- Consumes: Tasks 1-4 的全部产物。

- [ ] 停止旧的前台 `8765` 服务并启动打包 EXE。
- [ ] 验证桌面窗口出现、无控制台、`8765` 返回 200、专用 Chrome 打开 BOSS。
- [ ] 再次启动 EXE，验证单实例锁阻止第二个进程。
- [ ] 关闭桌面窗口，验证端口释放且数据、模型和 Chrome 配置仍存在。
- [ ] 运行 `python -m unittest discover -s tests -v` 与 `node --check app\static\app.js`，要求全部通过。
