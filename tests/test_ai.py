import tempfile
import unittest
from pathlib import Path

from app.ai import DraftService, build_prompt, message_fingerprint, quality_issues
from app.knowledge import KnowledgeStore


class FakeCompletion:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, messages):
        self.calls.append(messages)
        return self.responses.pop(0)


class AiDraftTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = KnowledgeStore(Path(self.directory.name) / "knowledge.db")
        self.store.create_entry(
            "是否还招",
            "目前岗位仍在招聘，但不能承诺一定录用。",
            "还招吗；岗位还有吗",
        )
        self.messages = [
            {"sender": "me", "text": "你好", "time": "10:00"},
            {"sender": "contact", "text": "这个岗位还招人吗？", "time": "10:01"},
        ]

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_prompt_contains_recent_chat_and_retrieved_knowledge(self):
        sources = self.store.search("还招人吗")
        prompt = build_prompt("操作工", self.messages, sources)

        self.assertIn("操作工", prompt[1]["content"])
        self.assertIn("候选人：这个岗位还招人吗？", prompt[1]["content"])
        self.assertIn("目前岗位仍在招聘", prompt[1]["content"])
        self.assertIn("最多提出一个问题", prompt[0]["content"])

    def test_quality_guard_accepts_short_natural_reply(self):
        self.assertEqual(quality_issues("还在招的，你之前做过操作工吗？"), [])

    def test_quality_guard_rejects_ai_style_and_unsafe_shapes(self):
        for text in (
            "根据您提供的信息，非常感谢您的咨询，如有其他问题请随时联系。",
            "## 回复\n- 目前还在招聘",
            "岗位在{工作地点}，工资是{薪资范围}。",
            "还在招。你在哪里？做过吗？什么时候能来？",
            "这是一段非常冗长的回复" * 12,
        ):
            with self.subTest(text=text):
                self.assertTrue(quality_issues(text))

    def test_generation_uses_one_rewrite_then_returns_ready_draft(self):
        complete = FakeCompletion(
            [
                "根据您提供的信息，非常感谢您的咨询，如有其他问题请随时联系。",
                "还在招的，你之前做过操作工吗？",
            ]
        )
        service = DraftService(self.store, complete=complete)

        result = service.generate("123", "操作工", self.messages)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["text"], "还在招的，你之前做过操作工吗？")
        self.assertEqual(len(complete.calls), 2)
        self.assertEqual(result["sources"][0]["title"], "是否还招")

    def test_follow_up_keeps_direct_answer_and_first_question(self):
        self.store.create_entry(
            "无经验候选人",
            "没经验可以先了解，是否接受新手要看现场要求。",
            "没经验可以吗；新手要不要",
        )
        complete = FakeCompletion(
            [
                "可以先了解一下。你之前主要做过什么工作？"
                "愿意学习并按安全规范操作吗？方便的话留个微信，我把岗位细节发你看看。"
            ]
        )
        service = DraftService(self.store, complete=complete)
        messages = self.messages + [
            {"sender": "me", "text": "你之前做过类似工作吗？", "time": "10:02"},
            {"sender": "contact", "text": "没有经验可以吗", "time": "10:03"},
        ]

        result = service.generate("123", "操作工", messages)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["text"], "可以先了解一下。你之前主要做过什么工作？")
        self.assertEqual(len(complete.calls), 1)

    def test_low_confidence_skips_model_and_requests_human_review(self):
        complete = FakeCompletion(["不会被调用"])
        service = DraftService(self.store, complete=complete)

        result = service.generate(
            "123",
            "操作工",
            [{"sender": "contact", "text": "量子纠缠怎么样", "time": "10:02"}],
        )

        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["text"], "")
        self.assertEqual(complete.calls, [])

    def test_same_incoming_message_reuses_cached_draft(self):
        complete = FakeCompletion(["还在招的，你之前做过操作工吗？"])
        service = DraftService(self.store, complete=complete)

        first = service.generate("123", "操作工", self.messages)
        second = service.generate("123", "操作工", self.messages)

        self.assertEqual(first, second)
        self.assertEqual(len(complete.calls), 1)
        self.assertEqual(
            first["fingerprint"], message_fingerprint("123", self.messages[-1])
        )

    def test_recruiter_reply_after_candidate_message_stops_draft(self):
        complete = FakeCompletion(["不会被调用"])
        service = DraftService(self.store, complete=complete)
        messages = self.messages + [
            {"sender": "me", "text": "还在招的", "time": "10:02"}
        ]

        result = service.generate("123", "操作工", messages)

        self.assertEqual(result["status"], "idle")
        self.assertEqual(complete.calls, [])


if __name__ == "__main__":
    unittest.main()
