import unittest
from unittest.mock import patch

from app.boss import (
    BossAdapter,
    BossError,
    is_verification_url,
    parse_contact_html,
    parse_message_html,
    parse_recommended_card_html,
    resolve_active_contact,
)


class FakeElement:
    def __init__(self, source="", text="", attrs=None, name_node=None):
        self.html = source
        self.text = text
        self.attrs = attrs or {}
        self.name_node = name_node
        self.clicked = False

    def attr(self, name):
        return self.attrs.get(name)

    def ele(self, selector, timeout=0):
        return self.name_node if selector == "css:.geek-name" else None

    def click(self):
        self.clicked = True


class VisibleElement(FakeElement):
    class States:
        is_displayed = True

    states = States()


class GreetingNoticePage:
    def __init__(self):
        self.notice = VisibleElement(text="已向牛人发送招呼")
        self.confirm = VisibleElement(text="知道了")

    def ele(self, selector, timeout=0):
        if selector == "text=已向牛人发送招呼":
            return self.notice
        if "知道了" in selector:
            return self.confirm
        return None


class NavigableBossPage:
    def __init__(self, url, tab_id="managed"):
        self.url = url
        self.tab_id = tab_id
        self.visited = []

    def get(self, url):
        self.visited.append(url)
        self.url = url

    def ele(self, selector, timeout=0):
        return FakeElement(text="退出登录") if selector == "tag:body" else None


class LoadingBossPage(NavigableBossPage):
    def __init__(self, url, tab_id="managed"):
        super().__init__(url, tab_id)
        self.login_checks = 0

    def get(self, url):
        super().get(url)
        self.login_checks = 0

    def ele(self, selector, timeout=0):
        if selector == "tag:body":
            self.login_checks += 1
            return FakeElement(text="")
        if selector == "css:.candidate-card-wrap" and self.login_checks >= 2:
            return VisibleElement()
        return None


class LoginRedirectPage(NavigableBossPage):
    def get(self, url):
        self.visited.append(url)
        self.url = "https://www.zhipin.com/web/user/?ka=header-login"


class SingleTabBrowser:
    def __init__(self, page):
        self.page = page
        self.tabs_count = 1
        self.created = []
        self.activated = []
        self.quit_calls = []

    def get_tabs(self):
        return [self.page]

    def new_tab(self, url):
        self.created.append(url)
        self.page.get(url)
        return self.page

    def activate_tab(self, tab_id):
        self.activated.append(tab_id)

    def quit(self, timeout=5, force=False, del_data=False):
        self.quit_calls.append((timeout, force, del_data))


class MultiTabBrowser(SingleTabBrowser):
    def __init__(self, pages):
        self.pages = pages
        self.tabs_count = len(pages)
        self.created = []
        self.activated = []

    def get_tabs(self):
        return self.pages


class RetryClickElement(FakeElement):
    def __init__(self, page, **kwargs):
        super().__init__(**kwargs)
        self.page = page

    def click(self):
        self.page.clicks += 1


class RetrySwitchPage:
    def __init__(self):
        self.clicks = 0
        name = FakeElement(text="蔡灿华", attrs={"title": "蔡灿华"})
        source = '<div class="geek-item" data-id="612923565-0"><span class="geek-name" title="蔡灿华">蔡灿华</span></div>'
        self.target = RetryClickElement(
            self, source=source, attrs={"data-id": "612923565-0"}, name_node=name
        )
        self.other = FakeElement(
            attrs={"data-id": "758794042-0"}, name_node=name
        )
        self.header = FakeElement(text="蔡灿华")

    def ele(self, selector, timeout=0):
        if selector.startswith('css:.geek-item[data-id='):
            return self.target
        if selector == "css:.geek-item.selected":
            return self.target if self.clicks >= 2 else self.other
        if selector == "css:.base-info-single-detial .name-box":
            return self.header
        return None


class FakePage:
    def __init__(self, target, selected, header):
        self.target = target
        self.selected = selected
        self.header = header

    def ele(self, selector, timeout=0):
        if selector.startswith('css:.geek-item[data-id='):
            return self.target
        if selector == "css:.geek-item.selected":
            return self.selected
        if selector == "css:.base-info-single-detial .name-box":
            return self.header
        return None


class DeletableContact(FakeElement):
    def __init__(self, page):
        super().__init__(attrs={"data-id": "123-0"})
        self.page = page
        self.operation = MoreMenuAction(page)

    def hover(self):
        self.page.hovered = True

    def ele(self, selector, timeout=0):
        if selector == "css:.user-operation":
            return self.operation
        return super().ele(selector, timeout)


class MoreMenuAction(VisibleElement):
    def __init__(self, page):
        super().__init__()
        self.page = page

    def click(self):
        self.clicked = True
        self.page.menu_open = True


class DeleteMenuAction(VisibleElement):
    def __init__(self, page):
        super().__init__(text="删除")
        self.page = page

    def click(self):
        self.clicked = True
        self.page.confirm_open = True


class ConfirmDeleteAction(VisibleElement):
    def __init__(self, page):
        super().__init__(text="确定")
        self.page = page

    def click(self):
        self.clicked = True
        self.page.deleted = True


class DeleteContactPage:
    def __init__(self):
        self.hovered = False
        self.menu_open = False
        self.confirm_open = False
        self.deleted = False
        self.target = DeletableContact(self)
        self.action = DeleteMenuAction(self)
        self.cancel = VisibleElement(text="取消")
        self.confirm = ConfirmDeleteAction(self)

    def ele(self, selector, timeout=0):
        if selector == 'css:.geek-item[data-id="123-0"]':
            return None if self.deleted else self.target
        return None

    def eles(self, selector, timeout=0):
        if selector == "css:.operation-item" and self.menu_open:
            return [self.action]
        if selector == "css:.boss-dialog__button" and self.confirm_open:
            return [self.cancel, self.confirm]
        return []


class BossParserTests(unittest.TestCase):
    def test_launch_and_close_manage_dedicated_browser(self):
        page = NavigableBossPage("about:blank")
        browser = SingleTabBrowser(page)
        adapter = BossAdapter()
        adapter._browser = browser

        result = adapter.launch()

        self.assertEqual(result, {"url": "https://www.zhipin.com/web/chat/index"})
        self.assertEqual(browser.created, ["https://www.zhipin.com/web/chat/index"])
        self.assertEqual(browser.activated, ["managed"])

        adapter.close()

        self.assertEqual(browser.quit_calls, [(5, False, False)])
        self.assertIsNone(adapter._browser)
        self.assertIsNone(adapter._managed_tab_id)

    def test_open_view_reuses_one_boss_tab_for_chat_and_recommend(self):
        page = NavigableBossPage("https://www.zhipin.com/web/chat/index")
        adapter = BossAdapter()
        adapter._browser = SingleTabBrowser(page)

        self.assertEqual(adapter.open_view("recommend")["view"], "recommend")
        self.assertEqual(adapter.open_view("chat")["view"], "chat")

        self.assertEqual(
            page.visited,
            [
                "https://www.zhipin.com/web/chat/recommend",
                "https://www.zhipin.com/web/chat/index",
            ],
        )
        self.assertEqual(adapter._browser.created, [])

    def test_open_view_waits_for_recommend_page_authenticated_content(self):
        page = LoadingBossPage("https://www.zhipin.com/web/chat/index")
        adapter = BossAdapter()
        adapter._browser = SingleTabBrowser(page)

        with patch("app.boss.time.sleep", return_value=None):
            result = adapter.open_view("recommend")

        self.assertEqual(result, {"view": "recommend"})
        self.assertGreaterEqual(page.login_checks, 2)

    def test_open_view_rejects_explicit_login_redirect(self):
        page = LoginRedirectPage("https://www.zhipin.com/web/chat/index")
        adapter = BossAdapter()
        adapter._browser = SingleTabBrowser(page)

        with self.assertRaises(BossError) as raised:
            adapter.open_view("recommend")

        self.assertEqual(raised.exception.code, "login_required")

    def test_open_view_keeps_one_managed_tab_when_both_views_exist(self):
        chat = NavigableBossPage("https://www.zhipin.com/web/chat/index", "chat-tab")
        recommend = NavigableBossPage(
            "https://www.zhipin.com/web/chat/recommend", "recommend-tab"
        )
        adapter = BossAdapter()
        adapter._browser = MultiTabBrowser([recommend, chat])

        adapter.open_view("recommend", activate=True)
        adapter.open_view("chat", activate=True)

        self.assertEqual(
            chat.visited,
            [
                "https://www.zhipin.com/web/chat/recommend",
                "https://www.zhipin.com/web/chat/index",
            ],
        )
        self.assertEqual(recommend.visited, [])
        self.assertEqual(adapter._browser.activated, ["chat-tab", "chat-tab"])

    def test_contact_switch_retries_one_missed_click(self):
        page = RetrySwitchPage()
        clock = iter([0, 0, 0, 2, 2, 6])

        with patch("app.boss.time.monotonic", side_effect=lambda: next(clock)), patch(
            "app.boss.time.sleep", return_value=None
        ):
            contact = BossAdapter()._select_contact(page, "612923565-0")

        self.assertEqual(contact["key"], "612923565-0")
        self.assertEqual(page.clicks, 2)

    def test_delete_contact_hovers_menu_and_verifies_removal(self):
        page = DeleteContactPage()
        adapter = BossAdapter()
        adapter._chat_page = lambda: page

        with patch("app.boss.time.monotonic", side_effect=[0, 0, 6]), patch(
            "app.boss.time.sleep", return_value=None
        ):
            result = adapter.delete_contact("123-0")

        self.assertEqual(result, {"deleted": True, "key": "123-0"})
        self.assertTrue(page.hovered)
        self.assertTrue(page.target.operation.clicked)
        self.assertTrue(page.action.clicked)
        self.assertTrue(page.confirm.clicked)

    def test_greeting_notice_is_acknowledged(self):
        page = GreetingNoticePage()

        acknowledged = BossAdapter()._acknowledge_greeting_notice(page)

        self.assertTrue(acknowledged)
        self.assertTrue(page.confirm.clicked)

    def test_recommended_card_uses_name_field_instead_of_salary(self):
        card = """
        <div class="candidate-card-wrap">
          <div class="salary-wrap">4-8K</div>
          <div class="name-wrap"><span class="name">张三</span></div>
          <div class="base-info">21岁 · 2年 · 高中</div>
          <div class="expect">东莞 · 操作工</div>
        </div>
        """

        candidate = parse_recommended_card_html(card)

        self.assertEqual(candidate["name"], "张三")
        self.assertEqual(candidate["summary"], "21岁 · 2年 · 高中 · 东莞 · 操作工")
        self.assertEqual(len(candidate["fingerprint"]), 20)

    def test_verification_url_is_detected(self):
        self.assertTrue(
            is_verification_url("https://www.zhipin.com/web/passport/zp/verify.html?code=36")
        )
        self.assertFalse(is_verification_url("https://www.zhipin.com/web/chat/index"))

    def test_parse_contact_extracts_stable_key_and_summary(self):
        html = """
        <div class="geek-item" data-id="767728911-0">
          <span class="time">10:18</span>
          <span class="geek-name" title="ccccccc">ccccccc</span>
          <span class="source-job" title="锯床操作工">锯床操作工</span>
          <span class="push-text">[送达]你好</span>
          <span class="badge-count">2</span>
        </div>
        """

        self.assertEqual(
            parse_contact_html(html),
            {
                "key": "767728911-0",
                "name": "ccccccc",
                "job": "锯床操作工",
                "time": "10:18",
                "preview": "[送达]你好",
                "unread": 2,
            },
        )

    def test_parse_outgoing_message_extracts_delivery_state(self):
        html = """
        <div class="message-item">
          <div class="message-time"><span class="time">10:18</span></div>
          <div class="item-myself">
            <i class="status status-delivery">送达</i>
            <span class="text-content">你好</span>
          </div>
        </div>
        """

        self.assertEqual(
            parse_message_html(html),
            {"sender": "me", "text": "你好", "time": "10:18", "status": "送达"},
        )

    def test_parse_incoming_and_system_messages(self):
        incoming = """
        <div class="message-item"><div class="item-friend">
          <span class="text-content">还招人吗？</span>
        </div></div>
        """
        system = """
        <div class="message-item"><div class="item-system">
          <div class="text"><span>请求交换微信已发送</span></div>
        </div></div>
        """

        self.assertEqual(parse_message_html(incoming)["sender"], "contact")
        self.assertEqual(parse_message_html(incoming)["text"], "还招人吗？")
        self.assertEqual(
            parse_message_html(system),
            {
                "sender": "system",
                "text": "请求交换微信已发送",
                "time": "",
                "status": "",
            },
        )

    def test_resolve_active_contact_accepts_refreshed_name_for_same_key(self):
        contact = {"key": "767728911-0", "name": "ccccccc", "job": "操作工"}

        resolved = resolve_active_contact(
            contact,
            selected_key="767728911-0",
            selected_name="蔡汉男",
            active_name="蔡汉男",
        )

        self.assertEqual(resolved["key"], "767728911-0")
        self.assertEqual(resolved["name"], "蔡汉男")

    def test_resolve_active_contact_rejects_different_selected_key(self):
        contact = {"key": "767728911-0", "name": "ccccccc", "job": "操作工"}

        with self.assertRaises(BossError):
            resolve_active_contact(
                contact,
                selected_key="another-contact",
                selected_name="蔡汉男",
                active_name="蔡汉男",
            )

    def test_passive_read_of_active_contact_does_not_click(self):
        source = """
        <div class="geek-item selected" data-id="767728911-0">
          <span class="geek-name" title="蔡汉男">蔡汉男</span>
          <span class="source-job" title="操作工">操作工</span>
        </div>
        """
        name = FakeElement(text="蔡汉男", attrs={"title": "蔡汉男"})
        target = FakeElement(
            source=source,
            attrs={"data-id": "767728911-0"},
            name_node=name,
        )
        page = FakePage(target, target, FakeElement(text="蔡汉男"))

        contact = BossAdapter()._select_contact(
            page, "767728911-0", allow_click=False
        )

        self.assertEqual(contact["name"], "蔡汉男")
        self.assertFalse(target.clicked)


if __name__ == "__main__":
    unittest.main()
