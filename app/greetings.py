from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .boss import BossError


DATETIME_FORMAT = "%Y-%m-%dT%H:%M"


def parse_minute(value: str) -> datetime:
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except (TypeError, ValueError) as exc:
        raise ValueError("时间格式必须精确到年月日、时和分") from exc


class PlanConflictError(ValueError):
    def __init__(self, conflict: dict[str, Any]):
        self.conflict = conflict
        super().__init__(
            f"与计划“{conflict['name']}”时间冲突（{conflict['start_at']} 至 {conflict['end_at']}）"
        )


class GreetingStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS greeting_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER NOT NULL DEFAULT 0,
                daily_limit INTEGER NOT NULL DEFAULT 30,
                hourly_limit INTEGER NOT NULL DEFAULT 4,
                start_at TEXT NOT NULL DEFAULT '',
                end_at TEXT NOT NULL DEFAULT '',
                paused_reason TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT OR IGNORE INTO greeting_settings (id) VALUES (1);
            CREATE TABLE IF NOT EXISTS greeting_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                daily_limit INTEGER NOT NULL DEFAULT 30,
                hourly_limit INTEGER NOT NULL DEFAULT 4,
                start_at TEXT NOT NULL,
                end_at TEXT NOT NULL,
                paused_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS greeting_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER,
                plan_name TEXT NOT NULL DEFAULT '',
                fingerprint TEXT NOT NULL DEFAULT '',
                candidate_name TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_greeting_logs_created_at
            ON greeting_logs(created_at);
            CREATE INDEX IF NOT EXISTS idx_greeting_plans_window
            ON greeting_plans(enabled, start_at, end_at);
            CREATE TABLE IF NOT EXISTS greeting_migrations (
                name TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self._migrate_legacy_settings()
        log_columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(greeting_logs)")
        }
        if "plan_id" not in log_columns:
            self._connection.execute("ALTER TABLE greeting_logs ADD COLUMN plan_id INTEGER")
        if "plan_name" not in log_columns:
            self._connection.execute(
                "ALTER TABLE greeting_logs ADD COLUMN plan_name TEXT NOT NULL DEFAULT ''"
            )
        self._connection.execute(
            """
            UPDATE greeting_logs
            SET plan_name = COALESCE(
                (SELECT name FROM greeting_plans WHERE id = greeting_logs.plan_id),
                ''
            )
            WHERE plan_name = '' AND plan_id IS NOT NULL
            """
        )

        migrated = self._connection.execute(
            "SELECT 1 FROM greeting_migrations WHERE name = 'multi_plan_v1'"
        ).fetchone()
        if not migrated:
            count = self._connection.execute(
                "SELECT COUNT(*) FROM greeting_plans"
            ).fetchone()[0]
            if not count:
                self._connection.execute(
                    """
                    INSERT INTO greeting_plans
                        (name, enabled, daily_limit, hourly_limit, start_at, end_at,
                         paused_reason, created_at, updated_at)
                    SELECT '默认招呼计划', enabled, daily_limit, hourly_limit,
                           start_at, end_at, paused_reason, updated_at, updated_at
                    FROM greeting_settings WHERE id = 1
                    """
                )
            self._connection.execute(
                "INSERT INTO greeting_migrations (name) VALUES ('multi_plan_v1')"
            )
        self._connection.commit()

    def _migrate_legacy_settings(self) -> None:
        columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(greeting_settings)")
        }
        if "start_at" not in columns:
            self._connection.execute(
                "ALTER TABLE greeting_settings ADD COLUMN start_at TEXT NOT NULL DEFAULT ''"
            )
        if "end_at" not in columns:
            self._connection.execute(
                "ALTER TABLE greeting_settings ADD COLUMN end_at TEXT NOT NULL DEFAULT ''"
            )
        window = self._connection.execute(
            "SELECT start_at, end_at FROM greeting_settings WHERE id = 1"
        ).fetchone()
        if not window["start_at"] or not window["end_at"]:
            now = datetime.now().replace(second=0, microsecond=0)
            if {"start_hour", "end_hour"}.issubset(columns):
                hours = self._connection.execute(
                    "SELECT start_hour, end_hour FROM greeting_settings WHERE id = 1"
                ).fetchone()
                start_at = now.replace(hour=int(hours["start_hour"]), minute=0)
                end_at = now.replace(hour=int(hours["end_hour"]), minute=0)
                if end_at <= start_at:
                    end_at += timedelta(days=1)
            else:
                start_at = now
                end_at = now + timedelta(days=1)
            self._connection.execute(
                "UPDATE greeting_settings SET start_at = ?, end_at = ? WHERE id = 1",
                (
                    start_at.strftime(DATETIME_FORMAT),
                    end_at.strftime(DATETIME_FORMAT),
                ),
            )

    @staticmethod
    def _plan(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["enabled"] = bool(item["enabled"])
        return item

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def list_plans(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM greeting_plans ORDER BY start_at, id"
            ).fetchall()
        return [self._plan(row) for row in rows]

    def get_plan(self, plan_id: int) -> dict[str, Any]:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM greeting_plans WHERE id = ?", (int(plan_id),)
            ).fetchone()
        if not row:
            raise KeyError(plan_id)
        return self._plan(row)

    def settings(self) -> dict[str, Any]:
        plans = self.list_plans()
        if not plans:
            raise KeyError("没有主动招呼计划")
        return plans[0]

    @staticmethod
    def _values(
        changes: dict[str, Any], current: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        now = datetime.now().replace(second=0, microsecond=0)
        defaults = current or {
            "name": "新招呼计划",
            "enabled": False,
            "daily_limit": 30,
            "hourly_limit": 4,
            "start_at": now.strftime(DATETIME_FORMAT),
            "end_at": (now + timedelta(days=1)).strftime(DATETIME_FORMAT),
            "paused_reason": "",
        }
        values = {
            "name": str(changes.get("name", defaults["name"])).strip(),
            "enabled": bool(changes.get("enabled", defaults["enabled"])),
            "daily_limit": int(changes.get("daily_limit", defaults["daily_limit"])),
            "hourly_limit": int(changes.get("hourly_limit", defaults["hourly_limit"])),
            "start_at": str(changes.get("start_at", defaults["start_at"])).strip(),
            "end_at": str(changes.get("end_at", defaults["end_at"])).strip(),
            "paused_reason": str(
                changes.get("paused_reason", defaults["paused_reason"])
            ).strip(),
        }
        if not 1 <= len(values["name"]) <= 40:
            raise ValueError("计划名称必须为 1 到 40 个字符")
        if not 1 <= values["daily_limit"] <= 200:
            raise ValueError("每日上限必须为 1 到 200")
        if not 1 <= values["hourly_limit"] <= 5:
            raise ValueError("每小时上限必须为 1 到 5")
        start_at = parse_minute(values["start_at"])
        end_at = parse_minute(values["end_at"])
        if end_at <= start_at:
            raise ValueError("结束时间必须晚于开始时间")
        values["start_at"] = start_at.strftime(DATETIME_FORMAT)
        values["end_at"] = end_at.strftime(DATETIME_FORMAT)
        if values["enabled"]:
            values["paused_reason"] = ""
        return values

    def _conflict(
        self, start_at: str, end_at: str, exclude_id: int | None = None
    ) -> dict[str, Any] | None:
        query = (
            "SELECT * FROM greeting_plans "
            "WHERE enabled = 1 AND start_at < ? AND end_at > ?"
        )
        params: list[Any] = [end_at, start_at]
        if exclude_id is not None:
            query += " AND id != ?"
            params.append(int(exclude_id))
        query += " ORDER BY start_at, id LIMIT 1"
        row = self._connection.execute(query, params).fetchone()
        return self._plan(row) if row else None

    def create_plan(self, **changes: Any) -> dict[str, Any]:
        values = self._values(changes)
        with self._lock:
            if values["enabled"]:
                conflict = self._conflict(values["start_at"], values["end_at"])
                if conflict:
                    raise PlanConflictError(conflict)
            cursor = self._connection.execute(
                """
                INSERT INTO greeting_plans
                    (name, enabled, daily_limit, hourly_limit, start_at, end_at,
                     paused_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    values["name"],
                    int(values["enabled"]),
                    values["daily_limit"],
                    values["hourly_limit"],
                    values["start_at"],
                    values["end_at"],
                    values["paused_reason"],
                ),
            )
            self._connection.commit()
            plan_id = int(cursor.lastrowid)
        return self.get_plan(plan_id)

    def update_plan(self, plan_id: int, **changes: Any) -> dict[str, Any]:
        with self._lock:
            current = self.get_plan(plan_id)
            values = self._values(changes, current)
            if values["enabled"]:
                conflict = self._conflict(
                    values["start_at"], values["end_at"], exclude_id=plan_id
                )
                if conflict:
                    raise PlanConflictError(conflict)
            self._connection.execute(
                """
                UPDATE greeting_plans SET name = ?, enabled = ?, daily_limit = ?,
                    hourly_limit = ?, start_at = ?, end_at = ?, paused_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    values["name"],
                    int(values["enabled"]),
                    values["daily_limit"],
                    values["hourly_limit"],
                    values["start_at"],
                    values["end_at"],
                    values["paused_reason"],
                    int(plan_id),
                ),
            )
            self._connection.commit()
        return self.get_plan(plan_id)

    def update_settings(self, **changes: Any) -> dict[str, Any]:
        return self.update_plan(self.settings()["id"], **changes)

    def delete_plan(self, plan_id: int) -> None:
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM greeting_plans WHERE id = ?", (int(plan_id),)
            )
            if not cursor.rowcount:
                raise KeyError(plan_id)
            self._connection.commit()

    def pause(self, plan_id: int, reason: str) -> None:
        with self._lock:
            cursor = self._connection.execute(
                """
                UPDATE greeting_plans SET enabled = 0, paused_reason = ?,
                    updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """,
                (reason.strip(), int(plan_id)),
            )
            if not cursor.rowcount:
                raise KeyError(plan_id)
            self._connection.commit()

    def add_log(
        self,
        status: str,
        now: datetime,
        plan_id: int | None = None,
        candidate: dict[str, Any] | None = None,
        reason: str = "",
    ) -> dict[str, Any]:
        candidate = candidate or {}
        with self._lock:
            plan_name = ""
            if plan_id is not None:
                plan = self._connection.execute(
                    "SELECT name FROM greeting_plans WHERE id = ?", (int(plan_id),)
                ).fetchone()
                plan_name = plan["name"] if plan else ""
            cursor = self._connection.execute(
                """
                INSERT INTO greeting_logs
                    (plan_id, plan_name, fingerprint, candidate_name, summary,
                     status, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    plan_name,
                    str(candidate.get("fingerprint", "")),
                    str(candidate.get("name", "")),
                    str(candidate.get("summary", "")),
                    status,
                    reason,
                    now.isoformat(timespec="seconds"),
                ),
            )
            self._connection.commit()
            row = self._connection.execute(
                "SELECT * FROM greeting_logs WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return dict(row)

    def counts(self, now: datetime) -> tuple[int, int]:
        day = now.strftime("%Y-%m-%d")
        hour = now.strftime("%Y-%m-%dT%H")
        with self._lock:
            today = self._connection.execute(
                "SELECT COUNT(*) FROM greeting_logs WHERE status = 'sent' AND substr(created_at, 1, 10) = ?",
                (day,),
            ).fetchone()[0]
            this_hour = self._connection.execute(
                "SELECT COUNT(*) FROM greeting_logs WHERE status = 'sent' AND substr(created_at, 1, 13) = ?",
                (hour,),
            ).fetchone()[0]
        return int(today), int(this_hour)

    def last_sent_at(self) -> datetime | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT created_at FROM greeting_logs WHERE status = 'sent' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return datetime.fromisoformat(row["created_at"]) if row else None

    def logs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT logs.*, COALESCE(NULLIF(logs.plan_name, ''), plans.name, '')
                    AS plan_name
                FROM greeting_logs AS logs
                LEFT JOIN greeting_plans AS plans ON plans.id = logs.plan_id
                ORDER BY logs.id DESC LIMIT ?
                """,
                (max(1, min(int(limit), 200)),),
            ).fetchall()
        return [dict(row) for row in rows]


class GreetingScheduler:
    PAUSE_CODES = {
        "verification_required",
        "login_required",
        "greeting_limit",
        "greet_unknown",
    }
    RESTORE_PAUSE_CODES = {
        "verification_required",
        "login_required",
        "chat_page_inactive",
    }

    def __init__(self, store: GreetingStore, boss: Any, interval_seconds: int = 30):
        self.store = store
        self.boss = boss
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._run_lock = threading.Lock()
        self._retry_after: datetime | None = None

    def _plan_status(
        self,
        plan: dict[str, Any],
        now: datetime,
        today_sent: int,
        hour_sent: int,
        last_sent: datetime | None,
    ) -> dict[str, Any]:
        start_at = parse_minute(plan["start_at"])
        end_at = parse_minute(plan["end_at"])
        spacing = timedelta(seconds=3600 / plan["hourly_limit"])
        within_window = start_at <= now < end_at
        manual_due = bool(
            plan["enabled"]
            and within_window
            and today_sent < plan["daily_limit"]
            and hour_sent < plan["hourly_limit"]
        )
        due = bool(
            manual_due
            and (last_sent is None or now >= last_sent + spacing)
            and (self._retry_after is None or now >= self._retry_after)
        )
        if not plan["enabled"]:
            window_state = "disabled"
        elif now < start_at:
            window_state = "pending"
        elif now >= end_at:
            window_state = "ended"
        else:
            window_state = "active"

        next_run = ""
        if plan["enabled"] and not due and now < end_at:
            candidate = max(now, start_at)
            if today_sent >= plan["daily_limit"]:
                candidate = max(
                    candidate,
                    (now + timedelta(days=1)).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ),
                )
            if hour_sent >= plan["hourly_limit"]:
                candidate = max(
                    candidate,
                    (now + timedelta(hours=1)).replace(
                        minute=0, second=0, microsecond=0
                    ),
                )
            if last_sent:
                candidate = max(candidate, last_sent + spacing)
            if self._retry_after:
                candidate = max(candidate, self._retry_after)
            if candidate < end_at:
                next_run = candidate.isoformat(timespec="seconds")

        return {
            **plan,
            "due": due,
            "manual_due": manual_due,
            "next_run": next_run,
            "window_state": window_state,
            "running": self._run_lock.locked(),
        }

    def list_plans(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now()
        today_sent, hour_sent = self.store.counts(now)
        last_sent = self.store.last_sent_at()
        return {
            "plans": [
                self._plan_status(plan, now, today_sent, hour_sent, last_sent)
                for plan in self.store.list_plans()
            ],
            "today_sent": today_sent,
            "hour_sent": hour_sent,
            "running": self._run_lock.locked(),
        }

    def plan_status(self, plan_id: int, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now()
        today_sent, hour_sent = self.store.counts(now)
        return self._plan_status(
            self.store.get_plan(plan_id),
            now,
            today_sent,
            hour_sent,
            self.store.last_sent_at(),
        )

    def status(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now()
        result = self.list_plans(now)
        if not result["plans"]:
            return {
                "settings": None,
                "today_sent": result["today_sent"],
                "hour_sent": result["hour_sent"],
                "due": False,
                "next_run": "",
                "window_state": "disabled",
                "running": result["running"],
            }
        plan = result["plans"][0]
        return {
            "settings": self.store.get_plan(plan["id"]),
            "today_sent": result["today_sent"],
            "hour_sent": result["hour_sent"],
            "due": plan["due"],
            "next_run": plan["next_run"],
            "window_state": plan["window_state"],
            "running": result["running"],
        }

    def create_plan(self, **changes: Any) -> dict[str, Any]:
        plan = self.store.create_plan(**changes)
        return self.plan_status(plan["id"])

    def update_plan(self, plan_id: int, **changes: Any) -> dict[str, Any]:
        self.store.update_plan(plan_id, **changes)
        return self.plan_status(plan_id)

    def update_settings(self, **changes: Any) -> dict[str, Any]:
        self.store.update_settings(**changes)
        return self.status()

    def delete_plan(self, plan_id: int) -> None:
        if not self._run_lock.acquire(blocking=False):
            raise ValueError("主动招呼正在执行，暂时不能删除计划")
        try:
            self.store.delete_plan(plan_id)
        finally:
            self._run_lock.release()

    def logs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.logs(limit)

    def run_once(
        self,
        plan_id: int | datetime | None = None,
        now: datetime | None = None,
        *,
        manual: bool = False,
    ) -> dict[str, Any]:
        if isinstance(plan_id, datetime) and now is None:
            now, plan_id = plan_id, None
        now = now or datetime.now()
        if not self._run_lock.acquire(blocking=False):
            raise ValueError("已有主动招呼任务正在执行")
        try:
            if plan_id is None:
                plans = self.store.list_plans()
                if not plans:
                    raise ValueError("没有可执行的主动招呼计划")
                plan_id = plans[0]["id"]
            plan_id = int(plan_id)
            status = self.plan_status(plan_id, now)
            if not status["manual_due" if manual else "due"]:
                raise ValueError("当前计划不在执行时段或额度已用完")

            restore_chat = True
            try:
                candidate = self.boss.greet_recommended()
                self.store.add_log("sent", now, plan_id, candidate=candidate)
                self._retry_after = None
                return candidate
            except BossError as exc:
                restore_chat = exc.code != "verification_required"
                self.store.add_log("failed", now, plan_id, reason=str(exc))
                if exc.code in self.PAUSE_CODES:
                    self.store.pause(plan_id, str(exc))
                else:
                    self._retry_after = now + timedelta(minutes=15)
                raise
            except Exception as exc:
                self.store.add_log("failed", now, plan_id, reason=str(exc))
                self._retry_after = now + timedelta(minutes=15)
                raise
            finally:
                if restore_chat:
                    try:
                        self.boss.open_view("chat")
                    except BossError as exc:
                        if exc.code in self.RESTORE_PAUSE_CODES:
                            self.store.pause(plan_id, f"返回沟通页失败：{exc}")
                        else:
                            self._retry_after = now + timedelta(minutes=15)
                    except Exception:
                        self._retry_after = now + timedelta(minutes=15)
        finally:
            self._run_lock.release()

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                due = next(
                    (plan for plan in self.list_plans()["plans"] if plan["due"]),
                    None,
                )
                if due:
                    self.run_once(due["id"])
            except Exception:
                pass

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="boss-greeting-scheduler", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
