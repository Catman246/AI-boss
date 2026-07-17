from __future__ import annotations

from pathlib import Path
from typing import Any


MODEL_NAME = "BAAI/bge-small-zh-v1.5"


class SemanticIndex:
    def __init__(
        self,
        path: Path,
        model_cache: Path,
        model_name: str = MODEL_NAME,
        table_name: str = "knowledge",
    ):
        self.path = Path(path)
        self.model_cache = Path(model_cache)
        self.model_name = model_name
        self.table_name = table_name
        self.path.mkdir(parents=True, exist_ok=True)
        self.model_cache.mkdir(parents=True, exist_ok=True)
        self._model = None
        self._db = None

    def _embedding_model(self):
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(
                model_name=self.model_name,
                cache_dir=str(self.model_cache),
                threads=2,
                lazy_load=True,
            )
        return self._model

    def _database(self):
        if self._db is None:
            import lancedb

            self._db = lancedb.connect(str(self.path))
        return self._db

    @staticmethod
    def _document(entry: dict[str, Any]) -> str:
        return "\n".join(
            value
            for value in (
                str(entry.get("title", "")).strip(),
                str(entry.get("keywords", "")).strip(),
                str(entry.get("content", "")).strip(),
            )
            if value
        )

    def warmup(self) -> int:
        vector = next(self._embedding_model().query_embed("招聘岗位咨询"))
        return len(vector)

    def sync(self, entries: list[dict[str, Any]]) -> None:
        database = self._database()
        if not entries:
            try:
                database.drop_table(self.table_name)
            except Exception:
                pass
            return
        documents = [self._document(entry) for entry in entries]
        vectors = list(self._embedding_model().passage_embed(documents))
        rows = [
            {
                "id": int(entry["id"]),
                "text": document,
                "vector": vector.tolist(),
            }
            for entry, document, vector in zip(entries, documents, vectors, strict=True)
        ]
        database.create_table(self.table_name, data=rows, mode="overwrite")

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        database = self._database()
        try:
            table = database.open_table(self.table_name)
        except Exception:
            return []
        vector = next(self._embedding_model().query_embed(query)).tolist()
        rows = (
            table.search(vector)
            .distance_type("cosine")
            .limit(max(1, min(limit, 30)))
            .to_list()
        )
        return [
            {
                "id": int(row["id"]),
                "score": round(max(0.0, min(1.0, 1.0 - float(row["_distance"]))), 4),
            }
            for row in rows
        ]
