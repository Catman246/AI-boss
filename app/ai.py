from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Callable

from .knowledge import KnowledgeStore


PROJECT_DIR = Path(__file__).parents[1]
BANNED_PHRASES = (
    "根据您提供的信息",
    "非常感谢您的咨询",
    "如有其他问题",
    "希望能帮助到您",
    "作为一个AI",
    "作为人工智能",
)


def load_env(path: Path = PROJECT_DIR / ".env") -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


def message_fingerprint(contact_key: str, message: dict[str, Any]) -> str:
    value = "\0".join(
        (contact_key, str(message.get("sender", "")), str(message.get("text", "")), str(message.get("time", "")))
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def clean_draft(text: str) -> str:
    text = (text or "").strip().strip('"“”')
    text = re.sub(r"^回复[:：]\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_draft(text: str) -> str:
    kept = []
    for sentence in re.findall(r"[^。！？!?]+[。！？!?]?", clean_draft(text)):
        kept.append(sentence.strip())
        if len(kept) == 2 or re.search(r"[？?]", sentence):
            break
    return clean_draft("".join(kept))


def quality_issues(text: str) -> list[str]:
    text = clean_draft(text)
    issues = []
    if not text:
        issues.append("草稿为空")
    if len(text) > 80:
        issues.append("草稿过长")
    if any(phrase.lower() in text.lower() for phrase in BANNED_PHRASES):
        issues.append("包含客服套话")
    if re.search(r"(^|\n)\s*(?:[-*#>]|\d+[.)])|`", text):
        issues.append("包含 Markdown")
    if re.search(r"[{}【】<>]", text):
        issues.append("包含未替换占位符")
    if len(re.findall(r"[？?]", text)) > 1:
        issues.append("一次提出多个问题")
    if len(re.findall(r"[。！？!?]", text)) > 2:
        issues.append("句子过多")
    return issues


def build_prompt(
    job: str,
    messages: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    agent: str = "boss",
) -> list[dict[str, str]]:
    role = (
        "你在 BOSS 上负责初次沟通、确认基本条件，并自然地推进候选人留下微信或手机号。"
        if agent == "boss"
        else "你在微信上负责后续答疑、确认求职意向，并推进确定具体面试时间和地点。"
    )
    system = f"""你是招聘人员的回复草稿助手。{role}只输出一条可以直接发送的中文消息。
要求：像真人聊天，简短直接，目标15到60个汉字，最多两句话，最多提出一个问题；不要Markdown、列表、解释、寒暄套话或重复候选人的原话；不得虚构薪资、地点、福利、名额、录用结果；知识不足时只问一个必要问题，不要承诺稍后一定处理。"""
    history = []
    labels = {"contact": "候选人", "me": "招聘方", "system": "系统"}
    for message in messages[-8:]:
        text = str(message.get("text", "")).strip()
        if text:
            history.append(f"{labels.get(message.get('sender'), '系统')}：{text}")
    knowledge = []
    for source in sources[:4]:
        knowledge.append(
            f"【{source['title']}】\n{str(source['content']).strip()[:1200]}"
        )
    user = (
        f"当前岗位：{job or '未确认'}\n\n"
        f"最近对话：\n{chr(10).join(history)}\n\n"
        f"可参考知识：\n{chr(10).join(knowledge)}\n\n"
        "根据知识和对话生成草稿。只写回复正文。"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


class DraftService:
    def __init__(
        self,
        store: KnowledgeStore,
        complete: Callable[[list[dict[str, str]]], str] | None = None,
    ):
        load_env()
        self.store = store
        self.model = os.getenv("KIMI_MODEL", "kimi-k2.6")
        self.base_url = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
        self.api_key = os.getenv("MOONSHOT_API_KEY", "")
        self._complete = complete or self._kimi_complete
        self._client = None
        self._cache: dict[str, dict[str, Any]] = {}

    def status(self) -> dict[str, Any]:
        return {"configured": bool(self.api_key), "model": self.model if self.api_key else ""}

    def _kimi_complete(self, messages: list[dict[str, str]]) -> str:
        if not self.api_key:
            raise RuntimeError("Kimi 尚未配置")
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=30.0,
                max_retries=0,
            )
        request: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 120,
        }
        if self.model in {"kimi-k2.6", "kimi-k2.5"}:
            request["extra_body"] = {"thinking": {"type": "disabled"}}
        response = self._client.chat.completions.create(**request)
        return response.choices[0].message.content or ""

    def generate(
        self,
        contact_key: str,
        job: str,
        messages: list[dict[str, Any]],
        force: bool = False,
        agent: str = "boss",
    ) -> dict[str, Any]:
        latest_chat = next(
            (
                message
                for message in reversed(messages)
                if message.get("sender") in {"contact", "me"}
            ),
            None,
        )
        if latest_chat is None:
            return {
                "status": "needs_review",
                "text": "",
                "reason": "当前会话没有候选人消息",
                "sources": [],
                "fingerprint": "",
            }
        if latest_chat.get("sender") != "contact":
            return {
                "status": "idle",
                "text": "",
                "reason": "招聘方已回复，暂无新草稿",
                "sources": [],
                "fingerprint": "",
            }
        incoming = latest_chat

        fingerprint = message_fingerprint(contact_key, incoming)
        if not force and fingerprint in self._cache:
            return dict(self._cache[fingerprint])

        sources = self.store.search(str(incoming.get("text", "")), limit=4)
        source_meta = [
            {"id": source["id"], "title": source["title"], "score": source["score"]}
            for source in sources
        ]
        if not sources:
            result = {
                "status": "needs_review",
                "text": "",
                "reason": "知识库没有可靠匹配，建议人工回复",
                "sources": [],
                "fingerprint": fingerprint,
            }
            self._cache[fingerprint] = result
            return dict(result)

        prompt = build_prompt(job, messages, sources, agent=agent)
        try:
            text = clean_draft(self._complete(prompt))
            issues = quality_issues(text)
            if issues:
                compacted = compact_draft(text)
                if not quality_issues(compacted):
                    text, issues = compacted, []
            if issues:
                rewrite = [
                    {
                        "role": "system",
                        "content": "把草稿改得像真人招聘聊天。只输出修改后的正文，15到60个汉字，最多两句话和一个问题，不要套话、Markdown或占位符。",
                    },
                    {
                        "role": "user",
                        "content": f"原草稿：{text}\n问题：{'；'.join(issues)}",
                    },
                ]
                text = clean_draft(self._complete(rewrite))
                issues = quality_issues(text)
        except Exception as exc:
            result = {
                "status": "error",
                "text": "",
                "reason": f"Kimi 生成失败：{type(exc).__name__}",
                "sources": source_meta,
                "fingerprint": fingerprint,
            }
            return result

        if issues:
            result = {
                "status": "needs_review",
                "text": "",
                "reason": "AI 草稿质量检查未通过，建议人工回复",
                "sources": source_meta,
                "fingerprint": fingerprint,
            }
        else:
            result = {
                "status": "ready",
                "text": text,
                "reason": "",
                "sources": source_meta,
                "fingerprint": fingerprint,
            }
        self._cache[fingerprint] = result
        return dict(result)
