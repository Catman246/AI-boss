from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Protocol


SECTION_PATTERN = re.compile(
    r"^##\s+(.+?)\s*$\n(.*?)(?=^##\s+|\Z)", re.MULTILINE | re.DOTALL
)
COMMON_PATTERN = re.compile(r"候选人常见说法[:：]\s*(.+)")


class SemanticBackend(Protocol):
    def sync(self, entries: list[dict[str, Any]]) -> None: ...

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]: ...


def _normalize(value: str) -> str:
    return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", value.lower()))


def _grams(value: str) -> set[str]:
    normalized = _normalize(value)
    if len(normalized) < 2:
        return {normalized} if normalized else set()
    return {normalized[index : index + 2] for index in range(len(normalized) - 1)}


def _score(query: str, title: str, content: str, keywords: str) -> float:
    normalized_query = _normalize(query)
    if not normalized_query:
        return 0.0

    query_grams = _grams(query)
    body = f"{title}\n{keywords}\n{content}"
    body_grams = _grams(body)
    gram_overlap = len(query_grams & body_grams) / max(len(query_grams), 1)
    char_overlap = len(set(normalized_query) & set(_normalize(body))) / len(
        set(normalized_query)
    )
    title_overlap = len(query_grams & _grams(title)) / max(len(query_grams), 1)
    keyword_parts = [
        _normalize(part)
        for part in re.split(r"[；;，,、\s]+", keywords)
        if _normalize(part)
    ]
    exact = 0.0
    if normalized_query in _normalize(body):
        exact = 0.55
    elif any(part in normalized_query or normalized_query in part for part in keyword_parts):
        exact = 0.45

    return round(min(1.0, exact + 0.28 * gram_overlap + 0.1 * char_overlap + 0.12 * title_overlap), 4)


class KnowledgeStore:
    def __init__(self, path: Path, semantic: SemanticBackend | None = None):
        self.path = Path(path)
        self.semantic = semantic
        self.semantic_error = ""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                content TEXT NOT NULL,
                keywords TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._connection.commit()

    def _sync_semantic(self) -> None:
        if self.semantic is None:
            return
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM knowledge_entries WHERE enabled = 1 ORDER BY id"
            ).fetchall()
        try:
            self.semantic.sync([self._entry(row) for row in rows])
            self.semantic_error = ""
        except Exception as exc:
            self.semantic_error = type(exc).__name__

    def semantic_status(self) -> dict[str, Any]:
        return {
            "configured": self.semantic is not None,
            "ready": self.semantic is not None and not self.semantic_error,
            "error": self.semantic_error,
        }

    def reindex(self) -> None:
        self._sync_semantic()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @staticmethod
    def _entry(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        entry = dict(row)
        entry["enabled"] = bool(entry["enabled"])
        return entry

    def seed_markdown(self, path: Path) -> int:
        text = Path(path).read_text(encoding="utf-8")
        inserted = 0
        with self._lock:
            for match in SECTION_PATTERN.finditer(text):
                title = match.group(1).strip()
                content = match.group(2).strip()
                common = COMMON_PATTERN.search(content)
                keywords = common.group(1).strip() if common else ""
                cursor = self._connection.execute(
                    """
                    INSERT OR IGNORE INTO knowledge_entries
                        (title, content, keywords, source)
                    VALUES (?, ?, ?, 'aihr-seed')
                    """,
                    (title, content, keywords),
                )
                inserted += cursor.rowcount
            self._connection.commit()
        if inserted:
            self._sync_semantic()
        return inserted

    def list_entries(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM knowledge_entries ORDER BY id"
            ).fetchall()
        return [self._entry(row) for row in rows]

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM knowledge_entries WHERE id = ?", (entry_id,)
            ).fetchone()
        return self._entry(row)

    @staticmethod
    def _validated(title: str, content: str, keywords: str) -> tuple[str, str, str]:
        title = title.strip()
        content = content.strip()
        keywords = keywords.strip()
        if not title or len(title) > 120:
            raise ValueError("知识标题长度必须为 1 到 120 个字符")
        if not content or len(content) > 20000:
            raise ValueError("知识内容长度必须为 1 到 20000 个字符")
        if len(keywords) > 1000:
            raise ValueError("关键词不能超过 1000 个字符")
        return title, content, keywords

    def create_entry(
        self, title: str, content: str, keywords: str = "", enabled: bool = True
    ) -> dict[str, Any]:
        title, content, keywords = self._validated(title, content, keywords)
        with self._lock:
            cursor = self._connection.execute(
                """
                INSERT INTO knowledge_entries (title, content, keywords, enabled)
                VALUES (?, ?, ?, ?)
                """,
                (title, content, keywords, int(enabled)),
            )
            self._connection.commit()
            entry_id = cursor.lastrowid
        self._sync_semantic()
        return self.get_entry(entry_id)

    def update_entry(self, entry_id: int, **changes: Any) -> dict[str, Any]:
        current = self.get_entry(entry_id)
        if current is None:
            raise KeyError(entry_id)
        title, content, keywords = self._validated(
            changes.get("title", current["title"]),
            changes.get("content", current["content"]),
            changes.get("keywords", current["keywords"]),
        )
        enabled = bool(changes.get("enabled", current["enabled"]))
        with self._lock:
            self._connection.execute(
                """
                UPDATE knowledge_entries
                SET title = ?, content = ?, keywords = ?, enabled = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title, content, keywords, int(enabled), entry_id),
            )
            self._connection.commit()
        self._sync_semantic()
        return self.get_entry(entry_id)

    def delete_entry(self, entry_id: int) -> None:
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM knowledge_entries WHERE id = ?", (entry_id,)
            )
            self._connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(entry_id)
        self._sync_semantic()

    def search(
        self, query: str, limit: int = 4, minimum_score: float = 0.18
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM knowledge_entries WHERE enabled = 1"
            ).fetchall()
        entries = {int(row["id"]): self._entry(row) for row in rows}
        lexical_scores = {
            entry_id: _score(query, entry["title"], entry["content"], entry["keywords"])
            for entry_id, entry in entries.items()
        }
        semantic_scores: dict[int, float] = {}
        if self.semantic is not None and query.strip():
            try:
                semantic_scores = {
                    int(item["id"]): float(item["score"])
                    for item in self.semantic.search(query, limit=max(limit * 3, 10))
                    if int(item["id"]) in entries and float(item["score"]) >= 0.55
                }
            except Exception:
                semantic_scores = {}

        results = []
        for entry_id, entry in entries.items():
            lexical = lexical_scores[entry_id]
            semantic = semantic_scores.get(entry_id, 0.0)
            semantic_weighted = semantic * 0.82 + lexical * 0.18
            score = round(max(lexical, semantic_weighted), 4)
            if score >= minimum_score:
                if semantic and semantic_weighted > lexical:
                    match_type = "semantic" if lexical < minimum_score else "hybrid"
                else:
                    match_type = "lexical"
                results.append({**entry, "score": score, "match_type": match_type})
        results.sort(key=lambda item: (-item["score"], item["id"]))
        return results[: max(1, min(limit, 10))]
