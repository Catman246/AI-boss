import unittest
from pathlib import Path


STATIC = Path(__file__).parents[1] / "app" / "static"


class StaticUiTests(unittest.TestCase):
    def test_html_contains_login_and_chat_workspaces(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        for element_id in (
            "login-view",
            "app-view",
            "contact-list",
            "message-list",
            "message-input",
            "send-button",
            "agent-boss",
            "agent-wechat",
            "candidate-context",
            "candidate-stage",
            "wechat-id",
            "private-contact",
            "interview-form",
            "task-drawer",
            "task-badge",
            "greeting-button",
            "greeting-drawer",
            "greeting-plan-list",
            "greeting-new-plan",
            "greeting-form",
            "greeting-plan-id",
            "greeting-plan-name",
            "greeting-enabled",
            "greeting-daily-limit",
            "greeting-hourly-limit",
            "greeting-start-at",
            "greeting-end-at",
            "greeting-plan-cancel",
            "model-button",
            "model-drawer",
            "model-form",
            "model-provider",
            "model-base-url",
            "model-api-key",
            "model-name",
            "model-test",
        ):
            self.assertIn(f'id="{element_id}"', html)

    def test_navigation_uses_readable_labels_and_switches_boss_views(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        css = (STATIC / "app.css").read_text(encoding="utf-8")
        javascript = (STATIC / "app.js").read_text(encoding="utf-8")

        for element_id, label in (
            ("conversation-button", "会话"),
            ("task-button", "交接任务"),
            ("greeting-button", "主动招呼"),
            ("knowledge-button", "知识库"),
            ("model-button", "AI 模型"),
            ("logout-button", "退出登录"),
        ):
            self.assertRegex(
                html,
                rf'id="{element_id}"[^>]*>[\s\S]*?<span class="rail-label">{label}</span>',
            )
        self.assertEqual(html.count('class="rail-icon"'), 6)
        self.assertIn("grid-template-columns: 132px", css)
        self.assertIn('/api/boss/view/chat', javascript)
        self.assertIn('/api/boss/view/recommend', javascript)

    def test_css_preserves_keyboard_and_reduced_motion_accessibility(self):
        css = (STATIC / "app.css").read_text(encoding="utf-8")
        self.assertIn(":focus-visible", css)
        self.assertIn("prefers-reduced-motion: reduce", css)

    def test_javascript_does_not_render_api_text_as_html(self):
        javascript = (STATIC / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", javascript)
        self.assertIn("textContent", javascript)

    def test_javascript_asset_is_versioned(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")

        self.assertRegex(html, r'/static/app\.js\?v=\d+')

    def test_app_grid_is_constrained_to_the_viewport(self):
        css = (STATIC / "app.css").read_text(encoding="utf-8")
        self.assertIn("grid-template-rows: minmax(0, 1fr);", css)
        self.assertIn("height: 100dvh;", css)

    def test_enter_sends_and_live_reads_are_passive(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        javascript = (STATIC / "app.js").read_text(encoding="utf-8")

        self.assertIn("Enter 发送 · Shift+Enter 换行", html)
        self.assertIn('event.key === "Enter" && !event.shiftKey', javascript)
        self.assertNotIn("event.ctrlKey", javascript)
        self.assertIn("/api/candidates?channel=${state.channel}", javascript)
        self.assertIn("setInterval(poll, 5000)", javascript)

    def test_ai_draft_requires_explicit_adoption_before_send(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        javascript = (STATIC / "app.js").read_text(encoding="utf-8")

        for element_id in (
            "ai-draft-panel",
            "ai-draft-status",
            "ai-draft-text",
            "ai-draft-sources",
            "adopt-draft",
            "regenerate-draft",
            "ignore-draft",
        ):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn("AI 草稿 · 发送前请审核", html)
        self.assertIn("/draft", javascript)
        self.assertIn("elements.messageInput.value = state.draft.text;", javascript)
        self.assertIn('addEventListener("click", adoptDraft)', javascript)

    def test_knowledge_drawer_has_crud_controls(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        javascript = (STATIC / "app.js").read_text(encoding="utf-8")

        for element_id in (
            "knowledge-button",
            "knowledge-drawer",
            "knowledge-list",
            "knowledge-form",
            "knowledge-title",
            "knowledge-keywords",
            "knowledge-content",
            "knowledge-enabled",
        ):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('api("/api/knowledge")', javascript)
        self.assertIn('method: "PATCH"', javascript)
        self.assertIn('method: "DELETE"', javascript)

    def test_ai_model_drawer_uses_masked_openai_compatible_config(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        javascript = (STATIC / "app.js").read_text(encoding="utf-8")

        self.assertIn("OpenAI 兼容接口", html)
        self.assertRegex(html, r'id="model-api-key"[^>]*type="password"')
        self.assertIn('api("/api/ai/config")', javascript)
        self.assertIn('api("/api/ai/config/test"', javascript)
        self.assertNotIn("innerHTML", javascript)

    def test_two_agents_share_candidate_api_and_review_tasks(self):
        javascript = (STATIC / "app.js").read_text(encoding="utf-8")

        self.assertIn("/api/candidates", javascript)
        self.assertIn("/api/tasks?status=pending_review", javascript)
        self.assertIn("/interviews", javascript)
        self.assertIn("/send", javascript)
        self.assertIn("/dismiss", javascript)

    def test_recommended_greeting_scheduler_has_plan_crud_and_history(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        javascript = (STATIC / "app.js").read_text(encoding="utf-8")

        self.assertRegex(html, r'id="greeting-start-at"[^>]*type="datetime-local"')
        self.assertRegex(html, r'id="greeting-end-at"[^>]*type="datetime-local"')
        self.assertNotIn("greeting-start-hour", html)
        self.assertNotIn("greeting-end-hour", html)
        self.assertIn("/api/greeting-plans", javascript)
        self.assertIn("/api/greetings/logs", javascript)
        self.assertIn("/run-once", javascript)
        self.assertIn("plan.manual_due", javascript)
        self.assertIn('run.textContent = "执行中…"', javascript)
        self.assertIn('method: "PATCH"', javascript)
        self.assertIn('method: "DELETE"', javascript)
        self.assertNotIn("/api/greetings/status", javascript)
        self.assertNotIn("/api/greetings/settings", javascript)

    def test_boss_contact_delete_is_hover_only_and_confirmed(self):
        css = (STATIC / "app.css").read_text(encoding="utf-8")
        javascript = (STATIC / "app.js").read_text(encoding="utf-8")

        self.assertIn("contact-actions", javascript)
        self.assertIn("deleteBossConversation", javascript)
        self.assertIn("/boss-conversation", javascript)
        self.assertIn("删除 BOSS 会话", javascript)
        self.assertIn(".contact-row:hover .contact-actions", css)

    def test_switching_contact_clears_previous_composer(self):
        javascript = (STATIC / "app.js").read_text(encoding="utf-8")
        select_contact = javascript.split("async function selectContact", 1)[1].split(
            "function adoptDraft", 1
        )[0]
        self.assertIn('elements.messageInput.value = "";', select_contact)
        self.assertIn("state.messages = [];", select_contact)
        self.assertIn("loadConversation({ activate: true })", select_contact)


if __name__ == "__main__":
    unittest.main()
