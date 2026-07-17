import tempfile
import unittest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.boss import BossError
from app.greetings import GreetingScheduler, GreetingStore, PlanConflictError, parse_minute


class FakeBoss:
    def __init__(self):
        self.calls = 0
        self.error = None
        self.views = []
        self.view_error = None

    def greet_recommended(self):
        self.calls += 1
        if self.error:
            raise self.error
        return {"fingerprint": f"candidate-{self.calls}", "name": f"候选人{self.calls}", "summary": "操作工"}

    def open_view(self, view, activate=False):
        self.views.append(view)
        if self.view_error:
            raise self.view_error
        return {"view": view}


class GreetingSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = GreetingStore(Path(self.directory.name) / "greetings.db")
        self.boss = FakeBoss()
        self.scheduler = GreetingScheduler(self.store, self.boss)

    def tearDown(self):
        self.scheduler.stop()
        self.store.close()
        self.directory.cleanup()

    def test_defaults_are_safe_and_disabled(self):
        status = self.scheduler.status()
        start_at = datetime.strptime(status["settings"]["start_at"], "%Y-%m-%dT%H:%M")
        end_at = datetime.strptime(status["settings"]["end_at"], "%Y-%m-%dT%H:%M")

        self.assertFalse(status["settings"]["enabled"])
        self.assertEqual(status["settings"]["hourly_limit"], 4)
        self.assertEqual(status["settings"]["daily_limit"], 30)
        self.assertLess(abs(datetime.now() - start_at), timedelta(minutes=2))
        self.assertEqual(end_at - start_at, timedelta(days=1))
        self.assertFalse(status["due"])

    def test_default_plan_can_be_created_edited_and_deleted(self):
        plans = self.store.list_plans()

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["name"], "默认招呼计划")

        created = self.store.create_plan(
            name="晚班计划",
            enabled=False,
            daily_limit=20,
            hourly_limit=3,
            start_at="2026-07-17T18:00",
            end_at="2026-07-17T23:00",
        )
        updated = self.store.update_plan(created["id"], name="夜班计划")

        self.assertEqual(updated["name"], "夜班计划")
        self.store.delete_plan(created["id"])
        self.assertEqual(len(self.store.list_plans()), 1)

    def test_deleting_last_plan_remains_empty_after_reopen(self):
        path = self.store.path
        self.store.delete_plan(self.store.settings()["id"])
        self.store.close()

        self.store = GreetingStore(path)

        self.assertEqual(self.store.list_plans(), [])

    def test_enabled_plan_overlap_is_rejected_but_adjacent_plan_is_allowed(self):
        current = self.store.settings()
        self.store.update_plan(
            current["id"],
            enabled=True,
            start_at="2026-07-17T09:00",
            end_at="2026-07-17T12:00",
        )

        with self.assertRaises(PlanConflictError) as raised:
            self.store.create_plan(
                name="冲突计划",
                enabled=True,
                daily_limit=30,
                hourly_limit=4,
                start_at="2026-07-17T11:59",
                end_at="2026-07-17T14:00",
            )

        self.assertEqual(raised.exception.conflict["id"], current["id"])
        adjacent = self.store.create_plan(
            name="下午计划",
            enabled=True,
            daily_limit=30,
            hourly_limit=4,
            start_at="2026-07-17T12:00",
            end_at="2026-07-17T18:00",
        )
        self.assertTrue(adjacent["enabled"])
        with self.assertRaises(PlanConflictError):
            self.store.update_plan(adjacent["id"], start_at="2026-07-17T11:59")

    def test_scheduler_runs_selected_plan_and_records_it(self):
        default = self.store.settings()
        self.store.update_plan(default["id"], enabled=False)
        plan = self.store.create_plan(
            name="上午计划",
            enabled=True,
            daily_limit=30,
            hourly_limit=4,
            start_at="2026-07-17T09:00",
            end_at="2026-07-17T12:00",
        )

        result = self.scheduler.run_once(plan["id"], datetime(2026, 7, 17, 10, 0))
        log = self.scheduler.logs()[0]

        self.assertEqual(result["fingerprint"], "candidate-1")
        self.assertEqual(log["plan_id"], plan["id"])
        self.assertEqual(log["plan_name"], "上午计划")

    def test_failure_pauses_only_selected_plan(self):
        first = self.store.settings()
        self.store.update_plan(
            first["id"],
            name="上午计划",
            enabled=True,
            start_at="2026-07-17T09:00",
            end_at="2026-07-17T12:00",
        )
        second = self.store.create_plan(
            name="下午计划",
            enabled=True,
            daily_limit=30,
            hourly_limit=4,
            start_at="2026-07-17T12:00",
            end_at="2026-07-17T18:00",
        )
        self.boss.error = BossError("登录失效", "login_required")

        with self.assertRaises(BossError):
            self.scheduler.run_once(first["id"], datetime(2026, 7, 17, 10, 0))

        self.assertFalse(self.store.get_plan(first["id"])["enabled"])
        self.assertTrue(self.store.get_plan(second["id"])["enabled"])

    def test_hourly_limit_cannot_exceed_five(self):
        with self.assertRaisesRegex(ValueError, "1 到 5"):
            self.store.update_settings(hourly_limit=6)

    def test_end_time_must_be_after_start_time(self):
        with self.assertRaisesRegex(ValueError, "结束时间必须晚于开始时间"):
            self.store.update_settings(
                start_at="2026-07-17T10:00", end_at="2026-07-17T09:59"
            )

    def test_due_respects_datetime_window_spacing_and_daily_limit(self):
        self.store.update_settings(
            enabled=True,
            daily_limit=2,
            hourly_limit=4,
            start_at="2026-07-16T10:00",
            end_at="2026-07-17T10:00",
        )
        now = datetime(2026, 7, 16, 10, 0)

        self.assertFalse(self.scheduler.status(now - timedelta(minutes=1))["due"])
        self.assertTrue(self.scheduler.status(now)["due"])
        self.scheduler.run_once(now)
        self.assertFalse(self.scheduler.status(now + timedelta(minutes=14))["due"])
        self.assertTrue(self.scheduler.status(now + timedelta(minutes=15))["due"])
        self.scheduler.run_once(now + timedelta(minutes=15))

        self.assertFalse(self.scheduler.status(now + timedelta(hours=1))["due"])
        self.assertFalse(self.scheduler.status(datetime(2026, 7, 17, 10, 0))["due"])

    def test_manual_run_ignores_spacing_but_still_consumes_quota(self):
        self.store.update_settings(
            enabled=True,
            daily_limit=30,
            hourly_limit=4,
            start_at="2026-07-16T09:00",
            end_at="2026-07-16T18:00",
        )
        plan_id = self.store.settings()["id"]
        now = datetime(2026, 7, 16, 10, 0)

        self.scheduler.run_once(plan_id, now)
        self.assertFalse(self.scheduler.plan_status(plan_id, now + timedelta(minutes=1))["due"])

        self.scheduler.run_once(plan_id, now + timedelta(minutes=1), manual=True)

        self.assertEqual(self.boss.calls, 2)
        self.assertEqual(self.store.counts(now + timedelta(minutes=1)), (2, 2))

    def test_manual_run_still_respects_plan_window(self):
        self.store.update_settings(
            enabled=True,
            start_at="2026-07-16T10:00",
            end_at="2026-07-16T18:00",
        )

        with self.assertRaises(ValueError):
            self.scheduler.run_once(
                self.store.settings()["id"],
                datetime(2026, 7, 16, 9, 59),
                manual=True,
            )

    def test_successful_greeting_restores_chat_view(self):
        self.store.update_settings(
            enabled=True,
            start_at="2026-07-16T09:00",
            end_at="2026-07-16T18:00",
        )

        result = self.scheduler.run_once(datetime(2026, 7, 16, 10, 0))

        self.assertEqual(result["name"], "候选人1")
        self.assertEqual(self.boss.views, ["chat"])

    def test_ordinary_failure_still_restores_chat_view(self):
        self.store.update_settings(
            enabled=True,
            start_at="2026-07-16T09:00",
            end_at="2026-07-16T18:00",
        )
        self.boss.error = BossError("推荐页暂时没有候选人", "no_candidates")

        with self.assertRaises(BossError):
            self.scheduler.run_once(datetime(2026, 7, 16, 10, 0))

        self.assertEqual(self.boss.views, ["chat"])

    def test_restore_failure_pauses_without_hiding_success(self):
        self.store.update_settings(
            enabled=True,
            start_at="2026-07-16T09:00",
            end_at="2026-07-16T18:00",
        )
        self.boss.view_error = BossError("沟通页恢复失败", "chat_page_inactive")

        result = self.scheduler.run_once(datetime(2026, 7, 16, 10, 0))

        self.assertEqual(result["name"], "候选人1")
        self.assertFalse(self.scheduler.status()["settings"]["enabled"])
        self.assertIn("沟通页恢复失败", self.scheduler.status()["settings"]["paused_reason"])

    def test_loading_restore_failure_does_not_pause_plan(self):
        self.store.update_settings(
            enabled=True,
            start_at="2026-07-16T09:00",
            end_at="2026-07-16T18:00",
        )
        self.boss.view_error = BossError("页面仍在加载", "page_loading")

        result = self.scheduler.run_once(datetime(2026, 7, 16, 10, 0))

        self.assertEqual(result["fingerprint"], "candidate-1")
        self.assertTrue(self.scheduler.status()["settings"]["enabled"])
        self.assertFalse(self.scheduler.status()["running"])

    def test_runtime_restore_failure_releases_lock_without_pausing(self):
        self.store.update_settings(
            enabled=True,
            start_at="2026-07-16T09:00",
            end_at="2026-07-16T18:00",
        )
        self.boss.view_error = RuntimeError("browser disconnected")

        result = self.scheduler.run_once(datetime(2026, 7, 16, 10, 0))

        self.assertEqual(result["fingerprint"], "candidate-1")
        self.assertTrue(self.scheduler.status()["settings"]["enabled"])
        self.assertFalse(self.scheduler.status()["running"])

    def test_runtime_greeting_failure_releases_lock_and_keeps_scheduler_available(self):
        self.store.update_settings(
            enabled=True,
            start_at="2026-07-16T09:00",
            end_at="2026-07-16T18:00",
        )
        self.boss.error = RuntimeError("browser disconnected")

        with self.assertRaises(RuntimeError):
            self.scheduler.run_once(datetime(2026, 7, 16, 10, 0))

        self.assertTrue(self.scheduler.status()["settings"]["enabled"])
        self.assertFalse(self.scheduler.status()["running"])
        self.assertEqual(self.scheduler.logs()[0]["status"], "failed")

    def test_delete_is_rejected_while_scheduler_is_running(self):
        plan_id = self.store.settings()["id"]
        self.scheduler._run_lock.acquire()
        try:
            with self.assertRaises(ValueError):
                self.scheduler.delete_plan(plan_id)
        finally:
            self.scheduler._run_lock.release()

        self.assertEqual(self.store.get_plan(plan_id)["id"], plan_id)

    def test_log_keeps_plan_name_after_plan_is_deleted(self):
        plan = self.store.settings()
        self.store.add_log(
            "sent",
            datetime(2026, 7, 16, 10, 0),
            plan_id=plan["id"],
            candidate={"name": "测试候选人"},
        )

        self.store.delete_plan(plan["id"])

        self.assertEqual(self.store.logs()[0]["plan_name"], plan["name"])

    def test_status_reports_running_state(self):
        self.scheduler._run_lock.acquire()
        try:
            self.assertTrue(self.scheduler.status()["running"])
        finally:
            self.scheduler._run_lock.release()

    def test_old_hour_schema_is_migrated_to_datetime_window(self):
        path = Path(self.directory.name) / "legacy.db"
        connection = sqlite3.connect(path)
        connection.executescript(
            """
            CREATE TABLE greeting_settings (
                id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                daily_limit INTEGER NOT NULL DEFAULT 30,
                hourly_limit INTEGER NOT NULL DEFAULT 4,
                start_hour INTEGER NOT NULL DEFAULT 9,
                end_hour INTEGER NOT NULL DEFAULT 18,
                paused_reason TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO greeting_settings (id) VALUES (1);
            """
        )
        connection.close()

        migrated = GreetingStore(path)
        settings = migrated.settings()
        migrated.close()

        self.assertIn("start_at", settings)
        self.assertIn("end_at", settings)
        self.assertNotIn("start_hour", settings)
        self.assertEqual(parse_minute(settings["start_at"]).hour, 9)
        self.assertEqual(parse_minute(settings["end_at"]).hour, 18)

    def test_verification_pauses_scheduler_without_retry(self):
        self.store.update_settings(
            enabled=True,
            start_at="2026-07-16T09:00",
            end_at="2026-07-16T18:00",
        )
        self.boss.error = BossError("需要安全验证", "verification_required")

        with self.assertRaises(BossError):
            self.scheduler.run_once(datetime(2026, 7, 16, 10, 0))

        status = self.scheduler.status(datetime(2026, 7, 16, 10, 1))
        self.assertFalse(status["settings"]["enabled"])
        self.assertIn("安全验证", status["settings"]["paused_reason"])
        self.assertEqual(self.boss.calls, 1)
        self.assertEqual(self.boss.views, [])


if __name__ == "__main__":
    unittest.main()
