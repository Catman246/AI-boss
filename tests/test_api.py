import unittest
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from app.boss import BossError
from app.greetings import PlanConflictError
from app.main import create_app
from app.recruiting import RecruitingStore


class FakeBoss:
    def __init__(self):
        self.sent = []
        self.reads = []
        self.views = []
        self.view_activations = []
        self.deleted = []
        self.delete_error = None

    def status(self):
        return {"connected": True, "logged_in": True, "message": "已连接"}

    def contacts(self, passive=False):
        self.reads.append(("contacts", passive))
        return [
            {
                "key": "123-0",
                "name": "测试联系人",
                "job": "操作工",
                "time": "10:18",
                "preview": "你好",
                "unread": 1,
            }
        ]

    def messages(self, key, passive=False):
        assert key == "123-0"
        self.reads.append(("messages", passive))
        return {
            "contact": {"key": key, "name": "测试联系人", "job": "操作工"},
            "messages": [
                {"sender": "contact", "text": "还招人吗？", "time": "10:17", "status": ""}
            ],
        }

    def send(self, key, text):
        self.sent.append((key, text))
        return {"sender": "me", "text": text, "time": "10:19", "status": "送达"}

    def open_view(self, view, activate=False):
        self.views.append(view)
        self.view_activations.append(activate)
        return {"view": view}

    def delete_contact(self, key):
        if self.delete_error:
            raise self.delete_error
        self.deleted.append(key)
        return {"deleted": True, "key": key}


class FakeKnowledge:
    def __init__(self):
        self.entries = {}
        self.next_id = 1

    def list_entries(self):
        return list(self.entries.values())

    def create_entry(self, title, content, keywords="", enabled=True):
        entry = {
            "id": self.next_id,
            "title": title,
            "content": content,
            "keywords": keywords,
            "enabled": enabled,
            "source": "manual",
        }
        self.entries[self.next_id] = entry
        self.next_id += 1
        return entry

    def update_entry(self, entry_id, **changes):
        if entry_id not in self.entries:
            raise KeyError(entry_id)
        self.entries[entry_id].update(changes)
        return self.entries[entry_id]

    def delete_entry(self, entry_id):
        if entry_id not in self.entries:
            raise KeyError(entry_id)
        del self.entries[entry_id]


class FakeDrafts:
    def __init__(self):
        self.calls = []

    def status(self):
        return {"configured": True, "model": "kimi-test"}

    def generate(self, contact_key, job, messages, force=False, agent="boss"):
        self.calls.append((contact_key, job, messages, force))
        return {
            "status": "ready",
            "text": "还在招的，你之前做过操作工吗？",
            "reason": "",
            "sources": [{"id": 1, "title": "是否还招", "score": 0.9}],
            "fingerprint": "abc123",
        }


class FakeGreetings:
    def __init__(self):
        self.runs = []
        self.plans = [{
            "id": 1,
            "name": "默认招呼计划",
            "enabled": False,
            "daily_limit": 30,
            "hourly_limit": 4,
            "start_at": "2026-07-16T10:00",
            "end_at": "2026-07-17T10:00",
            "paused_reason": "",
            "due": False,
            "next_run": "",
            "window_state": "disabled",
            "running": False,
        }]

    def list_plans(self):
        return {
            "plans": [dict(plan) for plan in self.plans],
            "today_sent": 0,
            "hour_sent": 0,
            "running": False,
        }

    def create_plan(self, **changes):
        plan = {
            **self.plans[0],
            **changes,
            "id": max(item["id"] for item in self.plans) + 1,
        }
        self.plans.append(plan)
        return dict(plan)

    def update_plan(self, plan_id, **changes):
        plan = next(item for item in self.plans if item["id"] == plan_id)
        plan.update(changes)
        return dict(plan)

    def delete_plan(self, plan_id):
        self.plans = [item for item in self.plans if item["id"] != plan_id]

    def run_once(self, plan_id, manual=False):
        self.runs.append((plan_id, manual))
        return {"fingerprint": "candidate-1", "name": "测试牛人", "summary": "操作工"}

    def logs(self, limit=50):
        return []


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.boss = FakeBoss()
        self.knowledge = FakeKnowledge()
        self.drafts = FakeDrafts()
        self.greetings = FakeGreetings()
        self.recruiting = RecruitingStore(Path(self.directory.name) / "recruiting.db")
        self.client = TestClient(
            create_app(
                self.boss,
                knowledge=self.knowledge,
                drafts=self.drafts,
                recruiting=self.recruiting,
                greetings=self.greetings,
            )
        )

    def tearDown(self):
        self.recruiting.close()
        self.directory.cleanup()

    def login(self):
        response = self.client.post(
            "/api/login", json={"username": "admin", "password": "123456"}
        )
        self.assertEqual(response.status_code, 200)

    def test_protected_route_rejects_anonymous_user(self):
        self.assertEqual(self.client.get("/api/contacts").status_code, 401)

    def test_index_is_not_cached(self):
        response = self.client.get("/")

        self.assertEqual(response.headers.get("cache-control"), "no-store")

    def test_default_services_use_injected_runtime_directory(self):
        with tempfile.TemporaryDirectory() as runtime, tempfile.TemporaryDirectory() as seeds:
            app = create_app(
                FakeBoss(), data_dir=Path(runtime), seed_dir=Path(seeds)
            )
            try:
                self.assertEqual(app.state.knowledge.path, Path(runtime) / "knowledge.db")
                self.assertEqual(app.state.recruiting.path, Path(runtime) / "recruiting.db")
                self.assertEqual(
                    app.state.greetings.store.path, Path(runtime) / "greetings.db"
                )
            finally:
                app.state.knowledge.close()
                app.state.recruiting.close()
                app.state.greetings.store.close()

    def test_boss_view_switch_is_authenticated_and_validated(self):
        self.assertEqual(self.client.post("/api/boss/view/chat").status_code, 401)
        self.login()

        response = self.client.post("/api/boss/view/recommend")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"view": "recommend"})
        self.assertEqual(self.boss.views, ["recommend"])
        self.assertEqual(self.boss.view_activations, [True])
        self.assertEqual(self.client.post("/api/boss/view/unknown").status_code, 422)

    def test_login_rejects_wrong_credentials(self):
        response = self.client.post(
            "/api/login", json={"username": "admin", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 401)

    def test_login_allows_access_to_contacts_and_messages(self):
        self.login()

        contacts = self.client.get("/api/contacts")
        conversation = self.client.get("/api/contacts/123-0/messages")

        self.assertEqual(contacts.status_code, 200)
        self.assertEqual(contacts.json()[0]["name"], "测试联系人")
        self.assertEqual(conversation.status_code, 200)
        self.assertEqual(conversation.json()["messages"][0]["text"], "还招人吗？")
        self.assertEqual(
            self.boss.reads,
            [("contacts", True), ("messages", True)],
        )

    def test_send_rejects_blank_text_without_calling_adapter(self):
        self.login()
        response = self.client.post(
            "/api/contacts/123-0/messages", json={"text": "   "}
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.boss.sent, [])

    def test_passive_reads_are_delegated_without_activation(self):
        self.login()

        self.client.get("/api/contacts?passive=true")
        self.client.get("/api/contacts/123-0/messages?passive=true")

        self.assertEqual(
            self.boss.reads,
            [("contacts", True), ("messages", True)],
        )

    def test_explicit_candidate_selection_activates_boss_conversation(self):
        self.login()
        candidate = self.client.get("/api/candidates?channel=boss").json()[0]
        self.boss.reads.clear()

        response = self.client.get(
            f"/api/candidates/{candidate['id']}/messages?channel=boss&activate=true"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.boss.reads, [("messages", False)])

    def test_send_delegates_one_trimmed_message(self):
        self.login()
        response = self.client.post(
            "/api/contacts/123-0/messages", json={"text": "  你好  "}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.boss.sent, [("123-0", "你好")])
        self.assertEqual(response.json()["status"], "送达")

    def test_logout_invalidates_session(self):
        self.login()
        self.assertEqual(self.client.post("/api/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/status").status_code, 401)

    def test_adapter_error_returns_structured_response(self):
        self.login()

        def fail_send(key, text):
            raise BossError("发送结果未知", "send_unknown")

        self.boss.send = fail_send
        response = self.client.post(
            "/api/contacts/123-0/messages", json={"text": "你好"}
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(), {"detail": "发送结果未知", "code": "send_unknown"}
        )

    def test_ai_status_does_not_expose_key(self):
        self.login()
        response = self.client.get("/api/ai/status")

        self.assertEqual(response.json(), {"configured": True, "model": "kimi-test"})
        self.assertNotIn("key", response.text.lower())

    def test_knowledge_crud_is_authenticated_and_validated(self):
        self.assertEqual(self.client.get("/api/knowledge").status_code, 401)
        self.login()

        invalid = self.client.post(
            "/api/knowledge", json={"title": "", "content": "内容"}
        )
        created = self.client.post(
            "/api/knowledge",
            json={"title": "岗位地址", "content": "地点在集美", "keywords": "地址"},
        )
        entry_id = created.json()["id"]
        updated = self.client.patch(
            f"/api/knowledge/{entry_id}", json={"enabled": False}
        )
        listed = self.client.get("/api/knowledge")
        deleted = self.client.delete(f"/api/knowledge/{entry_id}")

        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(created.status_code, 200)
        self.assertFalse(updated.json()["enabled"])
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(deleted.json(), {"deleted": True})

    def test_draft_reads_current_conversation_passively_and_never_sends(self):
        self.login()

        response = self.client.post("/api/contacts/123-0/draft", json={"force": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")
        self.assertEqual(response.json()["sources"][0]["title"], "是否还招")
        self.assertEqual(self.boss.sent, [])
        self.assertEqual(self.boss.reads, [("messages", True)])
        self.assertTrue(self.drafts.calls[0][3])

    def test_delete_boss_conversation_detaches_only_after_remote_success(self):
        self.login()
        candidate = self.client.get("/api/candidates?channel=boss").json()[0]

        response = self.client.delete(
            f"/api/candidates/{candidate['id']}/boss-conversation"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": True})
        self.assertEqual(self.boss.deleted, ["123-0"])
        self.assertIsNone(self.recruiting.get_candidate(candidate["id"])["boss_key"])

    def test_failed_boss_delete_keeps_local_link(self):
        self.login()
        candidate = self.client.get("/api/candidates?channel=boss").json()[0]
        self.boss.delete_error = BossError("删除结果未知", "delete_unknown")

        response = self.client.delete(
            f"/api/candidates/{candidate['id']}/boss-conversation"
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.recruiting.get_candidate(candidate["id"])["boss_key"], "123-0")

    def test_candidate_workspace_syncs_boss_and_links_wechat_identity(self):
        self.login()

        listed = self.client.get("/api/candidates?channel=boss")
        candidate_id = listed.json()[0]["id"]
        linked = self.client.patch(
            f"/api/candidates/{candidate_id}",
            json={"wechat_id": "wx_test", "private_contact": "13800000000", "stage": "private"},
        )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(linked.json()["boss_key"], "123-0")
        self.assertEqual(linked.json()["wechat_id"], "wx_test")

    def test_wechat_message_is_local_and_ai_draft_requires_review(self):
        self.login()
        created = self.client.post(
            "/api/candidates", json={"name": "微信候选人", "job": "操作工", "wechat_id": "wx_local"}
        ).json()

        message = self.client.post(
            f"/api/candidates/{created['id']}/messages",
            json={"channel": "wechat", "sender": "candidate", "text": "这个岗位还招吗"},
        )
        draft = self.client.post(
            f"/api/candidates/{created['id']}/draft",
            json={"channel": "wechat", "force": True},
        )

        self.assertEqual(message.status_code, 200)
        self.assertEqual(draft.status_code, 200)
        self.assertEqual(draft.json()["status"], "ready")
        self.assertEqual(self.boss.sent, [])

    def test_interview_task_is_sent_to_boss_only_after_explicit_review(self):
        self.login()
        candidate = self.client.get("/api/candidates?channel=boss").json()[0]
        interview = self.client.post(
            f"/api/candidates/{candidate['id']}/interviews",
            json={"starts_at": "2026-07-18 14:30", "location": "集美软件园"},
        )
        tasks = self.client.get("/api/tasks?status=pending_review").json()

        self.assertEqual(interview.status_code, 200)
        self.assertEqual(self.boss.sent, [])
        sent = self.client.post(f"/api/tasks/{tasks[0]['id']}/send", json={})

        self.assertEqual(sent.status_code, 200)
        self.assertEqual(sent.json()["task"]["status"], "sent")
        self.assertEqual(self.boss.sent[0][0], "123-0")
        self.assertIn("2026-07-18 14:30", self.boss.sent[0][1])

    def test_greeting_plan_crud_and_run_are_authenticated(self):
        self.assertEqual(self.client.get("/api/greeting-plans").status_code, 401)
        self.login()

        initial = self.client.get("/api/greeting-plans")
        created = self.client.post(
            "/api/greeting-plans",
            json={
                "name": "下午计划",
                "enabled": False,
                "daily_limit": 24,
                "hourly_limit": 4,
                "start_at": "2026-07-17T12:00",
                "end_at": "2026-07-17T18:00",
            },
        )
        plan_id = created.json()["id"]
        updated = self.client.patch(
            f"/api/greeting-plans/{plan_id}", json={"enabled": True}
        )
        executed = self.client.post(f"/api/greeting-plans/{plan_id}/run-once")
        deleted = self.client.delete(f"/api/greeting-plans/{plan_id}")

        self.assertFalse(initial.json()["plans"][0]["enabled"])
        self.assertEqual(created.status_code, 200)
        self.assertTrue(updated.json()["enabled"])
        self.assertEqual(executed.json()["fingerprint"], "candidate-1")
        self.assertEqual(self.greetings.runs, [(plan_id, True)])
        self.assertEqual(deleted.json(), {"deleted": True})

    def test_greeting_plan_conflict_returns_409_with_plan_name(self):
        self.login()

        def conflict(**_changes):
            raise PlanConflictError(self.greetings.plans[0])

        self.greetings.create_plan = conflict
        response = self.client.post(
            "/api/greeting-plans",
            json={
                "name": "冲突计划",
                "enabled": True,
                "daily_limit": 30,
                "hourly_limit": 4,
                "start_at": "2026-07-16T11:00",
                "end_at": "2026-07-16T12:00",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("默认招呼计划", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
