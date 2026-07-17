import tempfile
import unittest
from pathlib import Path

from app.knowledge import KnowledgeStore


SEED = """# 招聘客服话术知识库种子

## 01 初次打招呼

场景：候选人首次咨询岗位。
候选人常见说法：你好；还招吗；这个岗位现在有吗？
推荐回复：你好，岗位目前还在招。

## 02 薪资说明

场景：候选人直接问工资。
候选人常见说法：工资多少？一天多少钱？
推荐回复：目前薪资需要结合岗位确认。
"""


class KnowledgeStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.directory.name) / "knowledge.db"
        self.seed_path = Path(self.directory.name) / "seed.md"
        self.seed_path.write_text(SEED, encoding="utf-8")
        self.store = KnowledgeStore(self.db_path)

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_seed_import_is_idempotent(self):
        self.assertEqual(self.store.seed_markdown(self.seed_path), 2)
        self.assertEqual(self.store.seed_markdown(self.seed_path), 0)
        self.assertEqual(len(self.store.list_entries()), 2)

    def test_search_prioritizes_matching_recruitment_script(self):
        self.store.seed_markdown(self.seed_path)

        results = self.store.search("请问这个岗位还招人吗", limit=2)

        self.assertTrue(results)
        self.assertEqual(results[0]["title"], "01 初次打招呼")
        self.assertGreater(results[0]["score"], 0.2)

    def test_disabled_entry_is_not_retrieved(self):
        self.store.seed_markdown(self.seed_path)
        entry = self.store.list_entries()[0]
        self.store.update_entry(entry["id"], enabled=False)

        results = self.store.search("还招人吗")

        self.assertNotIn(entry["id"], [result["id"] for result in results])

    def test_crud_preserves_user_content(self):
        created = self.store.create_entry("岗位地址", "工作地点在集美区", "地址；哪里")
        updated = self.store.update_entry(created["id"], content="工作地点在集美软件园")

        self.assertEqual(updated["content"], "工作地点在集美软件园")
        self.assertEqual(self.store.get_entry(created["id"])["keywords"], "地址；哪里")
        self.store.delete_entry(created["id"])
        self.assertIsNone(self.store.get_entry(created["id"]))

    def test_unrelated_query_returns_low_confidence(self):
        self.store.seed_markdown(self.seed_path)
        self.assertEqual(self.store.search("量子纠缠实验结果"), [])

    def test_semantic_results_handle_paraphrases_and_keep_sqlite_as_source(self):
        class FakeSemantic:
            def __init__(self):
                self.entries = []

            def sync(self, entries):
                self.entries = list(entries)

            def search(self, query, limit=10):
                target = next(entry for entry in self.entries if "初次打招呼" in entry["title"])
                return [{"id": target["id"], "score": 0.86}]

        semantic = FakeSemantic()
        self.store.close()
        self.store = KnowledgeStore(self.db_path, semantic=semantic)
        self.store.seed_markdown(self.seed_path)

        results = self.store.search("请问目前还在招聘人员吗")

        self.assertEqual(results[0]["title"], "01 初次打招呼")
        self.assertEqual(results[0]["match_type"], "semantic")

    def test_disabled_entries_are_removed_from_semantic_index(self):
        class FakeSemantic:
            def __init__(self):
                self.entries = []

            def sync(self, entries):
                self.entries = list(entries)

            def search(self, query, limit=10):
                return []

        semantic = FakeSemantic()
        self.store.close()
        self.store = KnowledgeStore(self.db_path, semantic=semantic)
        self.store.seed_markdown(self.seed_path)
        entry = self.store.list_entries()[0]

        self.store.update_entry(entry["id"], enabled=False)

        self.assertNotIn(entry["id"], [item["id"] for item in semantic.entries])


if __name__ == "__main__":
    unittest.main()
