import tempfile
import unittest
from pathlib import Path

from app.recruiting import RecruitingStore


class RecruitingStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = RecruitingStore(Path(self.directory.name) / "recruiting.db")

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_boss_contact_and_wechat_identity_share_one_candidate(self):
        candidate = self.store.upsert_boss_contact(
            {"key": "boss-1", "name": "张三", "job": "操作工", "preview": "还招吗", "time": "10:20"}
        )

        linked = self.store.update_candidate(
            candidate["id"], wechat_id="wx_zhangsan", private_contact="13800000000"
        )

        self.assertEqual(linked["boss_key"], "boss-1")
        self.assertEqual(linked["wechat_id"], "wx_zhangsan")
        self.assertEqual(len(self.store.list_candidates()), 1)

    def test_channel_messages_are_kept_separate_but_use_shared_candidate(self):
        candidate = self.store.create_candidate("李四", "焊工", wechat_id="wx_lisi")
        self.store.add_message(candidate["id"], "wechat", "candidate", "明天下午方便")
        self.store.add_message(candidate["id"], "boss", "agent", "已加您微信")

        wechat = self.store.list_messages(candidate["id"], "wechat")
        boss = self.store.list_messages(candidate["id"], "boss")

        self.assertEqual([item["text"] for item in wechat], ["明天下午方便"])
        self.assertEqual([item["text"] for item in boss], ["已加您微信"])

    def test_detach_boss_contact_preserves_shared_candidate(self):
        candidate = self.store.upsert_boss_contact(
            {"key": "boss-1", "name": "张三", "job": "操作工"}
        )
        self.store.update_candidate(candidate["id"], wechat_id="wx_zhangsan")
        self.store.add_message(candidate["id"], "wechat", "candidate", "明天方便")

        detached = self.store.detach_boss_contact(candidate["id"])

        self.assertIsNone(detached["boss_key"])
        self.assertEqual(self.store.list_candidates(channel="boss"), [])
        self.assertEqual(
            self.store.list_candidates(channel="wechat")[0]["id"], candidate["id"]
        )
        self.assertEqual(
            self.store.list_messages(candidate["id"], "wechat")[0]["text"],
            "明天方便",
        )

    def test_confirmed_interview_creates_one_reviewable_boss_task(self):
        candidate = self.store.upsert_boss_contact(
            {"key": "boss-2", "name": "王五", "job": "钳工"}
        )

        first = self.store.schedule_interview(
            candidate["id"], "2026-07-18 14:30", "集美软件园三期"
        )
        second = self.store.schedule_interview(
            candidate["id"], "2026-07-18 14:30", "集美软件园三期"
        )
        tasks = self.store.list_tasks(status="pending_review")

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["source_agent"], "wechat")
        self.assertEqual(tasks[0]["target_agent"], "boss")
        self.assertEqual(tasks[0]["task_type"], "confirm_interview")
        self.assertIn("2026-07-18 14:30", tasks[0]["draft"])
        self.assertIn("集美软件园三期", tasks[0]["draft"])

    def test_task_status_records_human_review(self):
        candidate = self.store.upsert_boss_contact(
            {"key": "boss-3", "name": "赵六", "job": "普工"}
        )
        self.store.schedule_interview(candidate["id"], "2026-07-19 09:00", "集美厂区")
        task = self.store.list_tasks()[0]

        updated = self.store.update_task(task["id"], status="sent")

        self.assertEqual(updated["status"], "sent")
        self.assertTrue(updated["reviewed_at"])


if __name__ == "__main__":
    unittest.main()
