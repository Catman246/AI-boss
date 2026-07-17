from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


ALLOWED_STAGES = {"new", "contacted", "private", "interview", "hired", "closed"}
ALLOWED_CHANNELS = {"boss", "wechat"}
ALLOWED_SENDERS = {"candidate", "agent", "system"}


class RecruitingStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                job TEXT NOT NULL DEFAULT '',
                boss_key TEXT UNIQUE,
                wechat_id TEXT,
                private_contact TEXT NOT NULL DEFAULT '',
                stage TEXT NOT NULL DEFAULT 'new',
                tags TEXT NOT NULL DEFAULT '[]',
                notes TEXT NOT NULL DEFAULT '',
                last_message TEXT NOT NULL DEFAULT '',
                last_active TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS channel_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL REFERENCES candidates(id),
                channel TEXT NOT NULL,
                sender TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS interviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL REFERENCES candidates(id),
                starts_at TEXT NOT NULL,
                location TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'confirmed',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(candidate_id, starts_at, location)
            );
            CREATE TABLE IF NOT EXISTS agent_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL REFERENCES candidates(id),
                interview_id INTEGER REFERENCES interviews(id),
                source_agent TEXT NOT NULL,
                target_agent TEXT NOT NULL,
                task_type TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}',
                draft TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending_review',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_task_interview
            ON agent_tasks(interview_id, task_type);
            """
        )
        self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @staticmethod
    def _candidate(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        item = dict(row)
        try:
            item["tags"] = json.loads(item.get("tags") or "[]")
        except json.JSONDecodeError:
            item["tags"] = []
        return item

    @staticmethod
    def _task(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        item = dict(row)
        try:
            item["payload"] = json.loads(item.get("payload") or "{}")
        except json.JSONDecodeError:
            item["payload"] = {}
        return item

    def get_candidate(self, candidate_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
        return self._candidate(row)

    def get_by_boss_key(self, boss_key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM candidates WHERE boss_key = ?", (boss_key,)
            ).fetchone()
        return self._candidate(row)

    def create_candidate(
        self, name: str, job: str = "", wechat_id: str | None = None
    ) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValueError("候选人姓名不能为空")
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO candidates (name, job, wechat_id) VALUES (?, ?, ?)",
                (name, job.strip(), (wechat_id or "").strip() or None),
            )
            self._connection.commit()
        return self.get_candidate(cursor.lastrowid)

    def upsert_boss_contact(self, contact: dict[str, Any]) -> dict[str, Any]:
        boss_key = str(contact.get("key", "")).strip()
        if not boss_key:
            raise ValueError("BOSS 联系人缺少标识")
        name = str(contact.get("name", "")).strip() or "未命名候选人"
        job = str(contact.get("job", "")).strip()
        preview = str(contact.get("preview", "")).strip()
        active = str(contact.get("time", "")).strip()
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO candidates (name, job, boss_key, last_message, last_active)
                VALUES (?, ?, ?, ?, COALESCE(NULLIF(?, ''), CURRENT_TIMESTAMP))
                ON CONFLICT(boss_key) DO UPDATE SET
                    name = excluded.name,
                    job = CASE WHEN excluded.job = '' THEN candidates.job ELSE excluded.job END,
                    last_message = CASE WHEN excluded.last_message = '' THEN candidates.last_message ELSE excluded.last_message END,
                    last_active = CASE WHEN ? = '' THEN candidates.last_active ELSE excluded.last_active END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (name, job, boss_key, preview, active, active),
            )
            self._connection.commit()
        return self.get_by_boss_key(boss_key)

    def sync_boss_contacts(self, contacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for contact in contacts:
            self.upsert_boss_contact(contact)
        return self.list_candidates()

    def detach_boss_contact(self, candidate_id: int) -> dict[str, Any]:
        if self.get_candidate(candidate_id) is None:
            raise KeyError(candidate_id)
        with self._lock:
            self._connection.execute(
                "UPDATE candidates SET boss_key = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (candidate_id,),
            )
            self._connection.commit()
        return self.get_candidate(candidate_id)

    def list_candidates(self, channel: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM candidates"
        parameters: tuple[Any, ...] = ()
        if channel == "boss":
            query += " WHERE boss_key IS NOT NULL"
        elif channel == "wechat":
            query += " WHERE wechat_id IS NOT NULL OR private_contact != ''"
        query += " ORDER BY updated_at DESC, id DESC"
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return [self._candidate(row) for row in rows]

    def update_candidate(self, candidate_id: int, **changes: Any) -> dict[str, Any]:
        current = self.get_candidate(candidate_id)
        if current is None:
            raise KeyError(candidate_id)
        allowed = {"name", "job", "wechat_id", "private_contact", "stage", "tags", "notes"}
        values = {key: value for key, value in changes.items() if key in allowed}
        if "stage" in values and values["stage"] not in ALLOWED_STAGES:
            raise ValueError("候选人阶段无效")
        if "tags" in values:
            if not isinstance(values["tags"], list):
                raise ValueError("标签必须是数组")
            values["tags"] = json.dumps([str(item).strip() for item in values["tags"] if str(item).strip()], ensure_ascii=False)
        for key in {"name", "job", "wechat_id", "private_contact", "notes"} & values.keys():
            values[key] = str(values[key] or "").strip()
        if "name" in values and not values["name"]:
            raise ValueError("候选人姓名不能为空")
        if not values:
            return current
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._lock:
            self._connection.execute(
                f"UPDATE candidates SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (*values.values(), candidate_id),
            )
            self._connection.commit()
        return self.get_candidate(candidate_id)

    def add_message(
        self, candidate_id: int, channel: str, sender: str, text: str
    ) -> dict[str, Any]:
        if self.get_candidate(candidate_id) is None:
            raise KeyError(candidate_id)
        if channel not in ALLOWED_CHANNELS or sender not in ALLOWED_SENDERS:
            raise ValueError("消息渠道或发送方无效")
        text = text.strip()
        if not text or len(text) > 2000:
            raise ValueError("消息长度必须为 1 到 2000 个字符")
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO channel_messages (candidate_id, channel, sender, text) VALUES (?, ?, ?, ?)",
                (candidate_id, channel, sender, text),
            )
            self._connection.execute(
                "UPDATE candidates SET last_message = ?, last_active = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (text, candidate_id),
            )
            self._connection.commit()
            row = self._connection.execute(
                "SELECT * FROM channel_messages WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return dict(row)

    def list_messages(self, candidate_id: int, channel: str) -> list[dict[str, Any]]:
        if channel not in ALLOWED_CHANNELS:
            raise ValueError("消息渠道无效")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM channel_messages WHERE candidate_id = ? AND channel = ? ORDER BY id",
                (candidate_id, channel),
            ).fetchall()
        return [dict(row) for row in rows]

    def schedule_interview(
        self, candidate_id: int, starts_at: str, location: str
    ) -> dict[str, Any]:
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        starts_at, location = starts_at.strip(), location.strip()
        if not starts_at or not location:
            raise ValueError("面试时间和地点不能为空")
        with self._lock:
            self._connection.execute(
                "INSERT OR IGNORE INTO interviews (candidate_id, starts_at, location) VALUES (?, ?, ?)",
                (candidate_id, starts_at, location),
            )
            interview = self._connection.execute(
                "SELECT * FROM interviews WHERE candidate_id = ? AND starts_at = ? AND location = ?",
                (candidate_id, starts_at, location),
            ).fetchone()
            payload = {"candidate_id": candidate_id, "job": candidate["job"], "starts_at": starts_at, "location": location}
            draft = f"和您确认一下，面试安排在{starts_at}，地点是{location}，您按时到就可以。"
            self._connection.execute(
                """
                INSERT OR IGNORE INTO agent_tasks
                    (candidate_id, interview_id, source_agent, target_agent, task_type, payload, draft)
                VALUES (?, ?, 'wechat', 'boss', 'confirm_interview', ?, ?)
                """,
                (candidate_id, interview["id"], json.dumps(payload, ensure_ascii=False), draft),
            )
            self._connection.execute(
                "UPDATE candidates SET stage = 'interview', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (candidate_id,),
            )
            self._connection.commit()
        return dict(interview)

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT agent_tasks.*, candidates.name AS candidate_name,
                   candidates.job AS candidate_job, candidates.boss_key
            FROM agent_tasks JOIN candidates ON candidates.id = agent_tasks.candidate_id
        """
        parameters: tuple[Any, ...] = ()
        if status:
            query += " WHERE agent_tasks.status = ?"
            parameters = (status,)
        query += " ORDER BY agent_tasks.id DESC"
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return [self._task(row) for row in rows]

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT agent_tasks.*, candidates.name AS candidate_name,
                       candidates.job AS candidate_job, candidates.boss_key
                FROM agent_tasks JOIN candidates ON candidates.id = agent_tasks.candidate_id
                WHERE agent_tasks.id = ?
                """,
                (task_id,),
            ).fetchone()
        return self._task(row)

    def update_task(self, task_id: int, status: str) -> dict[str, Any]:
        if status not in {"pending_review", "approved", "sent", "dismissed", "failed"}:
            raise ValueError("任务状态无效")
        if self.get_task(task_id) is None:
            raise KeyError(task_id)
        with self._lock:
            self._connection.execute(
                """
                UPDATE agent_tasks SET status = ?,
                    reviewed_at = CASE WHEN ? = 'pending_review' THEN NULL ELSE CURRENT_TIMESTAMP END
                WHERE id = ?
                """,
                (status, status, task_id),
            )
            self._connection.commit()
        return self.get_task(task_id)
