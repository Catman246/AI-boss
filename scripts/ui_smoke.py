from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).parents[1]
ARTIFACTS = ROOT / "artifacts"


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        sent_requests = []

        def route_api(route):
            request = route.request
            url = request.url
            if url.endswith("/api/status"):
                route.fulfill(json={"connected": True, "logged_in": True, "message": "已连接"})
            elif url.endswith("/api/ai/status"):
                route.fulfill(json={"configured": True, "model": "kimi-k2.6"})
            elif url.endswith("/api/knowledge/status"):
                route.fulfill(json={"ready": True})
            elif url.endswith("/api/knowledge") and request.method == "GET":
                route.fulfill(
                    json=[
                        {
                            "id": 1,
                            "title": "初次打招呼",
                            "content": "岗位仍在招聘时，先确认候选人的相关经验。",
                            "category": "招聘话术",
                        }
                    ]
                )
            elif "/api/candidates/1/messages" in url and request.method == "GET":
                route.fulfill(
                    json=[
                        {"sender": "me", "text": "你好，想了解哪个岗位？", "time": "11:22", "status": "已读"},
                        {"sender": "contact", "text": "这个岗位还招人吗？", "time": "11:24", "status": ""},
                    ]
                )
            elif "/api/candidates/1/draft" in url:
                route.fulfill(
                    json={
                        "status": "ready",
                        "text": "还在招的，你之前做过操作工吗？",
                        "reason": "",
                        "sources": [{"id": 1, "title": "初次打招呼", "score": 0.86}],
                        "fingerprint": "smoke",
                    }
                )
            elif url.endswith("/api/candidates") or "/api/candidates?" in url:
                route.fulfill(
                    json=[
                        {
                            "id": 1,
                            "boss_key": "123-0",
                            "name": "林先生",
                            "job": "操作工",
                            "stage": "new",
                            "wechat_id": "",
                            "private_contact": "",
                            "tags": [],
                            "notes": "",
                            "last_active": "11:24",
                            "last_message": "这个岗位还招人吗？",
                            "unread": 1,
                        }
                    ]
                )
            elif "/api/contacts/123-0/messages" in url and request.method == "POST":
                sent_requests.append(url)
                route.fulfill(status=500, json={"detail": "smoke test must not send"})
            else:
                route.continue_()

        page.route("**/api/status", route_api)
        page.route("**/api/ai/status", route_api)
        page.route("**/api/knowledge**", route_api)
        page.route("**/api/candidates**", route_api)
        page.route("**/api/contacts**", route_api)
        page.goto("http://127.0.0.1:8765", wait_until="networkidle")
        page.screenshot(path=ARTIFACTS / "ai-login.png", full_page=True)
        page.locator("#username").fill("admin")
        page.locator("#password").fill("123456")
        page.locator('#login-form button[type="submit"]').click()
        page.locator('.contact-item[data-id="1"]').wait_for()
        page.locator('.contact-item[data-id="1"]').click()
        page.locator("#ai-draft-panel:not(.hidden)").wait_for()
        page.screenshot(path=ARTIFACTS / "ai-draft-review.png", full_page=True)
        page.locator("#adopt-draft").click()
        assert page.locator("#message-input").input_value() == "还在招的，你之前做过操作工吗？"
        assert sent_requests == []
        page.locator("#knowledge-button").click()
        page.locator("#knowledge-drawer:not(.hidden)").wait_for()
        page.locator(".knowledge-item").first.wait_for()
        page.wait_for_timeout(250)
        page.screenshot(path=ARTIFACTS / "knowledge-drawer.png", full_page=True)
        count = page.locator("#knowledge-count").inner_text()
        print(json.dumps({"draft_adopted": True, "sent": 0, "knowledge": count}, ensure_ascii=True))
        browser.close()


if __name__ == "__main__":
    main()
