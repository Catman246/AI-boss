from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import msvcrt
import os
import shutil
import socket
import sys
import threading
import time
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import uvicorn


APP_TITLE = "招聘助手"
APP_DIR_NAME = "RecruitingConsole"
HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}/"


class AlreadyRunning(RuntimeError):
    pass


def app_home(environ: Mapping[str, str] | None = None) -> Path:
    values = os.environ if environ is None else environ
    local = values.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / APP_DIR_NAME


def resource_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    return Path(frozen_root) if frozen_root else Path(__file__).resolve().parent


def project_root() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def prepare_user_data(home: Path, resources: Path, project: Path) -> None:
    data = home / "data"
    for directory in (data, home / "logs", home / "WebView"):
        directory.mkdir(parents=True, exist_ok=True)

    source_model = resources / "data" / "models" / "fastembed"
    target_model = data / "models" / "fastembed"
    if source_model.is_dir() and not target_model.exists():
        target_model.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_model, target_model)

    source_data = project / "data"
    for name in ("knowledge.db", "recruiting.db", "greetings.db"):
        source = source_data / name
        target = data / name
        if source.is_file() and not target.exists():
            shutil.copy2(source, target)

    source_env = project / ".env"
    target_env = home / ".env"
    if source_env.is_file() and not target_env.exists():
        shutil.copy2(source_env, target_env)


def acquire_instance(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        handle.close()
        raise AlreadyRunning(APP_TITLE) from exc
    return handle


def server_ready(url: str = URL) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=0.5) as response:
            return response.status == 200
    except OSError:
        return False


def port_available(host: str = HOST, port: int = PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


class DesktopRuntime:
    def __init__(self, boss: Any, fastapi_app: Any, host: str = HOST, port: int = PORT):
        self.boss = boss
        self.url = f"http://{host}:{port}/"
        config = uvicorn.Config(
            fastapi_app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
        self.server = uvicorn.Server(config)
        self.thread: threading.Thread | None = None

    def start_server(self) -> None:
        if not port_available(port=self.server.config.port):
            raise RuntimeError(f"端口 {self.server.config.port} 已被占用，请先关闭旧服务")
        self.thread = threading.Thread(
            target=self.server.run, name="recruiting-api", daemon=True
        )
        self.thread.start()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if server_ready(self.url):
                return
            if not self.thread.is_alive():
                break
            time.sleep(0.1)
        raise RuntimeError("本地服务启动失败")

    def stop(self) -> None:
        self.server.should_exit = True
        if self.thread is not None:
            self.thread.join(8)
        self.boss.close()


def configure_logging(home: Path) -> None:
    handler = RotatingFileHandler(
        home / "logs" / "desktop.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def show_error(message: str) -> None:
    import ctypes

    ctypes.windll.user32.MessageBoxW(0, message, APP_TITLE, 0x10)


def main() -> int:
    home = app_home()
    prepare_user_data(home, resource_root(), project_root())
    configure_logging(home)
    instance = None
    runtime = None

    try:
        instance = acquire_instance(home / "desktop.lock")

        from app.ai import load_env
        from app.boss import BossAdapter
        from app.main import create_app

        load_env(home / ".env")
        boss = BossAdapter()
        fastapi_app = create_app(
            boss=boss,
            data_dir=home / "data",
            seed_dir=resource_root() / "data",
        )
        runtime = DesktopRuntime(boss, fastapi_app)
        runtime.start_server()

        import webview

        window = webview.create_window(
            APP_TITLE,
            runtime.url,
            width=1600,
            height=960,
            screen=webview.screens[0],
            min_size=(1320, 760),
            resizable=True,
            background_color="#edf2f0",
        )

        def launch_boss() -> None:
            try:
                boss.launch()
            except Exception:
                logging.getLogger(__name__).exception("BOSS Chrome 启动失败")

        webview.start(
            launch_boss,
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(home / "WebView"),
        )
        return 0
    except AlreadyRunning:
        show_error("招聘助手已经在运行。")
        return 0
    except Exception as exc:
        logging.getLogger(__name__).exception("桌面程序启动失败")
        show_error(f"启动失败：{exc}\n\n详细信息已写入本地日志。")
        return 1
    finally:
        if runtime is not None:
            try:
                runtime.stop()
            except Exception:
                logging.getLogger(__name__).exception("桌面程序清理失败")
        if instance is not None:
            instance.close()


if __name__ == "__main__":
    raise SystemExit(main())
