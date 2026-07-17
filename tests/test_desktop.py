import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI

import desktop


class FakeThread:
    def __init__(self):
        self.joins = []

    def join(self, timeout=None):
        self.joins.append(timeout)


class FakeBoss:
    def __init__(self):
        self.closed = 0

    def close(self):
        self.closed += 1


class DesktopTests(unittest.TestCase):
    def test_app_home_uses_local_app_data(self):
        self.assertEqual(
            desktop.app_home({"LOCALAPPDATA": r"C:\Users\test\AppData\Local"}),
            Path(r"C:\Users\test\AppData\Local") / "RecruitingConsole",
        )

    def test_prepare_user_data_copies_only_missing_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            resources = root / "bundle"
            project = root / "project"

            (resources / "data" / "models" / "fastembed").mkdir(parents=True)
            (resources / "data" / "models" / "fastembed" / "model.bin").write_bytes(
                b"model"
            )
            (project / "data").mkdir(parents=True)
            (project / "data" / "knowledge.db").write_bytes(b"knowledge")
            (project / "data" / "recruiting.db").write_bytes(b"new")
            (project / ".env").write_text("MOONSHOT_API_KEY=secret\n", encoding="utf-8")
            (home / "data").mkdir(parents=True)
            (home / "data" / "recruiting.db").write_bytes(b"keep")

            desktop.prepare_user_data(home, resources, project)

            self.assertEqual((home / "data" / "knowledge.db").read_bytes(), b"knowledge")
            self.assertEqual((home / "data" / "recruiting.db").read_bytes(), b"keep")
            self.assertEqual(
                (home / "data" / "models" / "fastembed" / "model.bin").read_bytes(),
                b"model",
            )
            self.assertEqual(
                (home / ".env").read_text(encoding="utf-8"),
                "MOONSHOT_API_KEY=secret\n",
            )
            self.assertTrue((home / "logs").is_dir())
            self.assertTrue((home / "WebView").is_dir())

    def test_file_lock_rejects_second_instance_and_releases_on_close(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "desktop.lock"
            first = desktop.acquire_instance(path)
            try:
                with self.assertRaises(desktop.AlreadyRunning):
                    desktop.acquire_instance(path)
            finally:
                first.close()

            released = desktop.acquire_instance(path)
            released.close()

    def test_runtime_stop_stops_server_thread_and_browser(self):
        runtime = desktop.DesktopRuntime.__new__(desktop.DesktopRuntime)
        runtime.server = type("Server", (), {"should_exit": False})()
        runtime.thread = FakeThread()
        runtime.boss = FakeBoss()

        runtime.stop()

        self.assertTrue(runtime.server.should_exit)
        self.assertEqual(runtime.thread.joins, [8])
        self.assertEqual(runtime.boss.closed, 1)

    def test_runtime_can_be_created_without_console_streams(self):
        with (
            patch.object(desktop.sys, "stdout", None),
            patch.object(desktop.sys, "stderr", None),
        ):
            runtime = desktop.DesktopRuntime(FakeBoss(), FastAPI(), port=18765)

        self.assertIsNone(runtime.server.config.log_config)


if __name__ == "__main__":
    unittest.main()
