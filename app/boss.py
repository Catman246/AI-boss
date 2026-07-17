from __future__ import annotations

import re
import hashlib
import os
import threading
import time
from pathlib import Path
from typing import Any

from lxml import html as lxml_html


CHAT_URL = "https://www.zhipin.com/web/chat/index"
RECOMMEND_URL = "https://www.zhipin.com/web/chat/recommend"
PROFILE_DIR = Path(
    os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
) / "DrissionPage" / "Chrome9333"
CONTACT_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


class BossError(RuntimeError):
    def __init__(self, message: str, code: str = "boss_error"):
        super().__init__(message)
        self.code = code


def is_verification_url(url: str) -> bool:
    return "/passport/zp/verify" in url or "/verify.html" in url


def _text(node: Any, selector: str) -> str:
    matches = node.cssselect(selector)
    return " ".join(matches[0].text_content().split()) if matches else ""


def parse_contact_html(source: str) -> dict[str, Any]:
    root = lxml_html.fromstring(source)
    key = root.get("data-id", "")
    if not key or not CONTACT_KEY.fullmatch(key):
        raise ValueError("联系人缺少有效的 data-id")

    name_nodes = root.cssselect(".geek-name")
    job_nodes = root.cssselect(".source-job")
    name = (name_nodes[0].get("title") or name_nodes[0].text_content()).strip() if name_nodes else ""
    job = (job_nodes[0].get("title") or job_nodes[0].text_content()).strip() if job_nodes else ""

    unread = 0
    for selector in (".badge-count", ".unread-count", ".badge-num"):
        value = _text(root, selector)
        if value:
            match = re.search(r"\d+", value)
            unread = int(match.group()) if match else 1
            break

    return {
        "key": key,
        "name": name,
        "job": job,
        "time": _text(root, ".time"),
        "preview": _text(root, ".push-text"),
        "unread": unread,
    }


def parse_message_html(source: str) -> dict[str, str]:
    root = lxml_html.fromstring(source)
    if root.cssselect(".item-myself"):
        sender = "me"
        text = _text(root, ".text-content")
    elif root.cssselect(".item-friend"):
        sender = "contact"
        text = _text(root, ".text-content")
    elif root.cssselect(".item-system"):
        sender = "system"
        text = _text(root, ".item-system .text")
    else:
        sender = "system"
        text = " ".join(root.text_content().split())

    return {
        "sender": sender,
        "text": text,
        "time": _text(root, ".message-time .time"),
        "status": _text(root, ".status"),
    }


def parse_recommended_card_html(source: str) -> dict[str, str]:
    root = lxml_html.fromstring(source)
    text = " ".join(root.text_content().split())
    details = [_text(root, selector) for selector in (".base-info", ".expect")]
    return {
        "fingerprint": hashlib.sha256(text.encode("utf-8")).hexdigest()[:20],
        "name": _text(root, ".name-wrap .name") or "未命名候选人",
        "summary": " · ".join(detail for detail in details if detail),
    }


def resolve_active_contact(
    contact: dict[str, Any],
    selected_key: str,
    selected_name: str,
    active_name: str,
) -> dict[str, Any]:
    if (
        selected_key != contact["key"]
        or not selected_name
        or selected_name != active_name
    ):
        raise BossError("当前聊天对象校验失败，消息未发送", "recipient_mismatch")

    resolved = dict(contact)
    resolved["name"] = active_name
    return resolved


class BossAdapter:
    def __init__(self, port: int = 9333, profile_dir: Path = PROFILE_DIR):
        self.port = port
        self.profile_dir = profile_dir
        self._browser = None
        self._managed_tab_id = None
        self._lock = threading.RLock()

    def _connect(self):
        if self._browser is not None:
            try:
                self._browser.tabs_count
                return self._browser
            except Exception:
                self._browser = None
                self._managed_tab_id = None

        from DrissionPage import Chromium, ChromiumOptions

        options = (
            ChromiumOptions()
            .set_local_port(self.port)
            .set_user_data_path(str(self.profile_dir))
        )
        self._browser = Chromium(options)
        return self._browser

    def _managed_page(self, target_url: str | None = None, create: bool = True):
        browser = self._connect()
        tabs = browser.get_tabs()
        verification = next(
            (tab for tab in tabs if is_verification_url(tab.url)), None
        )
        if verification:
            return verification

        page = next(
            (
                tab
                for tab in tabs
                if getattr(tab, "tab_id", None) == self._managed_tab_id
            ),
            None,
        )
        if page is None:
            page = next((tab for tab in tabs if "/web/chat/index" in tab.url), None)
        if page is None:
            page = next((tab for tab in tabs if "zhipin.com" in tab.url), None)
        if page is None:
            if not create:
                raise BossError("未打开 BOSS 页面", "boss_page_missing")
            page = browser.new_tab(target_url or CHAT_URL)
        self._managed_tab_id = getattr(page, "tab_id", None)
        if target_url and target_url not in page.url:
            page.get(target_url)
        return page

    def _page(self, navigate: bool = True):
        return self._managed_page(CHAT_URL if navigate else None, create=navigate)

    def launch(self) -> dict[str, str]:
        with self._lock:
            page = self._managed_page(CHAT_URL)
            self._connect().activate_tab(page.tab_id)
            return {"url": page.url}

    def close(self) -> None:
        with self._lock:
            browser = self._browser
            self._browser = None
            self._managed_tab_id = None
            if browser is not None:
                browser.quit()

    @staticmethod
    def _login_state(page) -> str:
        url = (page.url or "").lower()
        if any(value in url for value in ("/web/user/", "/passport/login", "/user/login")):
            return "logged_out"

        body = page.ele("tag:body", timeout=0.5)
        if body and "退出登录" in body.text:
            return "logged_in"
        if any(
            page.ele(selector, timeout=0.1)
            for selector in (
                "css:.geek-item",
                "css:.candidate-card-wrap",
                "css:button.btn-greet",
            )
        ):
            return "logged_in"
        return "loading"

    @classmethod
    def _wait_for_login_state(cls, page, timeout: float = 8) -> str:
        deadline = time.monotonic() + timeout
        while True:
            state = cls._login_state(page)
            if state != "loading" or time.monotonic() >= deadline:
                return state
            time.sleep(0.2)

    def status(self) -> dict[str, Any]:
        with self._lock:
            try:
                page = self._page(navigate=False)
                if is_verification_url(page.url):
                    return {
                        "connected": True,
                        "logged_in": False,
                        "message": "BOSS 要求安全验证，实时读取已暂停",
                    }
                login_state = self._wait_for_login_state(page)
                logged_in = login_state == "logged_in"
                return {
                    "connected": True,
                    "logged_in": logged_in,
                    "message": (
                        "BOSS 已连接"
                        if logged_in
                        else "需要登录 BOSS"
                        if login_state == "logged_out"
                        else "BOSS 页面正在加载"
                    ),
                }
            except Exception as exc:
                return {
                    "connected": False,
                    "logged_in": False,
                    "message": f"浏览器连接失败：{exc}",
                }

    def _chat_page(self, passive: bool = False):
        page = self._page(navigate=not passive)
        if is_verification_url(page.url):
            raise BossError(
                "BOSS 要求安全验证，系统已暂停所有操作",
                "verification_required",
            )
        login_state = self._wait_for_login_state(page)
        if login_state == "logged_out":
            raise BossError("BOSS 登录已失效，请在 Chrome 中重新登录", "login_required")
        if "/web/chat/index" not in page.url:
            raise BossError(
                "BOSS 聊天页未打开，实时读取已暂停",
                "chat_page_inactive",
            )
        if login_state == "loading":
            raise BossError("BOSS 聊天页尚未加载完成，请稍后重试", "page_loading")
        return page

    def contacts(self, passive: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            page = self._chat_page(passive=passive)
            elements = page.eles("css:.geek-item", timeout=3)
            return [parse_contact_html(element.html) for element in elements]

    def _select_contact(
        self, page, key: str, allow_click: bool = True
    ) -> dict[str, Any]:
        if not CONTACT_KEY.fullmatch(key):
            raise BossError("联系人标识无效", "invalid_contact")

        element = page.ele(f'css:.geek-item[data-id="{key}"]', timeout=5)
        if not element:
            raise BossError("联系人不存在或列表已刷新", "contact_not_found")

        contact = parse_contact_html(element.html)

        def active_contact() -> dict[str, Any]:
            selected = page.ele("css:.geek-item.selected", timeout=0.3)
            header = page.ele(
                "css:.base-info-single-detial .name-box", timeout=0.3
            )
            if not selected or not header:
                raise BossError("当前会话尚未打开", "conversation_not_active")
            name_node = selected.ele("css:.geek-name", timeout=0.2)
            selected_name = (
                (name_node.attr("title") or name_node.text).strip()
                if name_node
                else ""
            )
            return resolve_active_contact(
                contact,
                selected.attr("data-id") or "",
                selected_name,
                header.text.strip(),
            )

        try:
            return active_contact()
        except BossError:
            if not allow_click:
                raise BossError(
                    "当前 BOSS 会话已切换，实时读取已暂停",
                    "conversation_not_active",
                )

        element.click()
        clicked_at = time.monotonic()
        deadline = clicked_at + 5
        retry_at = clicked_at + 1
        retried = False
        while time.monotonic() < deadline:
            try:
                return active_contact()
            except BossError:
                if not retried and time.monotonic() >= retry_at:
                    refreshed = page.ele(
                        f'css:.geek-item[data-id="{key}"]', timeout=1
                    )
                    if refreshed:
                        refreshed.click()
                    retried = True
                    time.sleep(0.15)
                    try:
                        return active_contact()
                    except BossError:
                        pass
            time.sleep(0.15)

        raise BossError("当前聊天对象校验失败，消息未发送", "recipient_mismatch")

    @staticmethod
    def _messages_from(page) -> list[dict[str, str]]:
        elements = page.eles("css:.message-item", timeout=3)
        return [message for element in elements if (message := parse_message_html(element.html))["text"]]

    def messages(self, key: str, passive: bool = False) -> dict[str, Any]:
        with self._lock:
            page = self._chat_page(passive=passive)
            contact = self._select_contact(page, key, allow_click=not passive)
            return {"contact": contact, "messages": self._messages_from(page)}

    def send(self, key: str, text: str) -> dict[str, str]:
        text = text.strip()
        if not text:
            raise BossError("消息不能为空", "invalid_message")

        with self._lock:
            page = self._chat_page()
            self._select_contact(page, key)
            before = len(page.eles("css:.message-item", timeout=3))
            editor = page.ele("css:.boss-chat-editor-input", timeout=5)
            if not editor or not editor.states.is_displayed:
                raise BossError("消息输入框不可用", "composer_unavailable")
            if editor.text.strip():
                raise BossError("输入框中已有未发送内容，消息未发送", "composer_not_empty")

            editor.input(text)
            button = page.ele("css:.submit", timeout=5)
            if not button or not button.states.is_displayed or button.text.strip() != "发送":
                editor.clear()
                raise BossError("发送按钮不可用", "send_unavailable")
            button.click()

            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                elements = page.eles("css:.message-item", timeout=1)
                if len(elements) > before:
                    message = parse_message_html(elements[-1].html)
                    if message["sender"] == "me" and message["text"] == text:
                        return message
                time.sleep(0.25)

            raise BossError("发送结果未知，请在 BOSS 页面确认；系统不会自动重试", "send_unknown")

    def delete_contact(self, key: str) -> dict[str, Any]:
        if not CONTACT_KEY.fullmatch(key):
            raise BossError("联系人标识无效", "invalid_contact")

        with self._lock:
            page = self._chat_page()
            selector = f'css:.geek-item[data-id="{key}"]'
            contact = page.ele(selector, timeout=5)
            if not contact:
                raise BossError("联系人不存在或列表已刷新", "contact_not_found")

            contact.hover()
            operation = contact.ele("css:.user-operation", timeout=2)
            if not operation or not operation.states.is_displayed:
                raise BossError(
                    "BOSS 会话菜单结构已变化，删除已取消", "delete_unavailable"
                )
            operation.click()
            actions = [
                item
                for item in page.eles("css:.operation-item", timeout=2)
                if item.states.is_displayed and item.text.strip() == "删除"
            ]
            if len(actions) != 1:
                raise BossError(
                    "BOSS 会话菜单结构已变化，删除已取消", "delete_unavailable"
                )
            actions[0].click()

            confirmations = [
                item
                for item in page.eles("css:.boss-dialog__button", timeout=0.8)
                if item.states.is_displayed
                and item.text.strip() in {"确定", "确认", "确认删除"}
            ]
            if len(confirmations) == 1:
                confirmations[0].click()

            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if is_verification_url(getattr(page, "url", "")):
                    raise BossError(
                        "BOSS 要求安全验证，删除结果未知", "verification_required"
                    )
                if not page.ele(selector, timeout=0.3):
                    return {"deleted": True, "key": key}
                time.sleep(0.2)

            raise BossError(
                "删除结果未知，请在 BOSS 页面确认；系统不会自动重试",
                "delete_unknown",
            )

    def _recommend_page(self):
        page = self._managed_page(RECOMMEND_URL)
        if is_verification_url(page.url):
            raise BossError("BOSS 要求安全验证，主动招呼已暂停", "verification_required")
        login_state = self._wait_for_login_state(page)
        if login_state == "logged_out":
            raise BossError("BOSS 登录已失效，主动招呼已暂停", "login_required")
        if login_state == "loading":
            raise BossError("BOSS 推荐牛人页尚未加载完成，请稍后重试", "page_loading")
        return page

    def open_view(self, view: str, activate: bool = False) -> dict[str, str]:
        if view not in {"chat", "recommend"}:
            raise ValueError("BOSS 页面只能切换到 chat 或 recommend")
        with self._lock:
            page = self._chat_page() if view == "chat" else self._recommend_page()
            if activate:
                self._connect().activate_tab(page.tab_id)
        return {"view": view}

    @staticmethod
    def _acknowledge_greeting_notice(page) -> bool:
        notice = page.ele("text=已向牛人发送招呼", timeout=2)
        if not notice or not notice.states.is_displayed:
            return False

        confirm = page.ele(
            "xpath://button[normalize-space(.)='知道了']", timeout=1
        ) or page.ele("text=知道了", timeout=0.5)
        if not confirm or not confirm.states.is_displayed:
            raise BossError("招呼已发送，但确认弹窗无法关闭", "greet_unknown")
        confirm.click()
        return True

    def greet_recommended(self) -> dict[str, str]:
        with self._lock:
            page = self._recommend_page()
            buttons = [
                button
                for button in page.eles("css:button.btn-greet", timeout=8)
                if button.states.is_displayed and button.text.strip() == "打招呼"
            ]
            if not buttons:
                body = page.ele("tag:body", timeout=2)
                text = body.text if body else ""
                if any(value in text for value in ("沟通人数已达上限", "打招呼次数已用完", "今日权益已用完")):
                    raise BossError("BOSS 今日主动沟通额度已用完", "greeting_limit")
                raise BossError("推荐牛人页面当前没有可打招呼对象", "no_candidates")

            button = buttons[0]
            card = button.parent(5)
            if not card or "candidate-card-wrap" not in (card.attr("class") or ""):
                raise BossError("推荐牛人卡片结构已变化，主动招呼已暂停", "greet_unknown")
            candidate = parse_recommended_card_html(card.html)

            button.click()
            time.sleep(1.5)
            if any(is_verification_url(tab.url) for tab in self._connect().get_tabs()):
                raise BossError("BOSS 要求安全验证，主动招呼已暂停", "verification_required")
            acknowledged = self._acknowledge_greeting_notice(page)
            if acknowledged:
                return candidate
            try:
                unchanged = button.states.is_displayed and button.text.strip() == "打招呼"
            except Exception:
                unchanged = False
            if unchanged:
                raise BossError("打招呼结果未知，系统不会自动重试", "greet_unknown")
            return candidate
