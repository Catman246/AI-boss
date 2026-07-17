from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from .knowledge import KnowledgeStore


PROJECT_DIR = Path(__file__).parents[1]
AI_ENV_KEYS = ("AI_PROVIDER", "AI_BASE_URL", "AI_API_KEY", "AI_MODEL")
BANNED_PHRASES = (
    "根据您提供的信息",
    "非常感谢您的咨询",
    "如有其他问题",
    "希望能帮助到您",
    "作为一个AI",
    "作为人工智能",
)


def read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip()
    return values


def load_env(path: Path = PROJECT_DIR / ".env") -> None:
    for name, value in read_env(path).items():
        os.environ.setdefault(name, value)


def write_env(path: Path, updates: Mapping[str, str]) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    written = set()
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name = line.split("=", 1)[0].strip()
        if name in updates:
            lines[index] = f"{name}={updates[name]}"
            written.add(name)
    lines.extend(f"{name}={updates[name]}" for name in AI_ENV_KEYS if name not in written)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary.replace(path)


def normalize_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("Base URL 必须是有效的 http 或 https 地址")
    path = parts.path.rstrip("/")
    if path.endswith("/chat/completions"):
        path = path[: -len("/chat/completions")]
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


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
        config_path: Path | None = None,
        environ: Mapping[str, str] | None = None,
    ):
        self.config_path = Path(config_path or PROJECT_DIR / ".env")
        if environ is None:
            load_env(self.config_path)
            environ = os.environ
        self.environ = environ
        self.store = store
        self._complete = complete or self._provider_complete
        self._client = None
        self._client_signature: tuple[str, str] | None = None
        self._cache: dict[str, dict[str, Any]] = {}

    def status(self) -> dict[str, Any]:
        config = self.config()
        return {
            "configured": config["configured"],
            "model": config["model"] if config["configured"] else "",
            "provider": config["provider"],
        }

    def _config(self) -> dict[str, str]:
        values = dict(self.environ)
        values.update(read_env(self.config_path))
        legacy = any(values.get(name) for name in ("MOONSHOT_API_KEY", "KIMI_BASE_URL", "KIMI_MODEL"))
        return {
            "provider": values.get("AI_PROVIDER", "Kimi" if legacy else "").strip(),
            "base_url": values.get("AI_BASE_URL", values.get("KIMI_BASE_URL", "")).strip(),
            "api_key": values.get("AI_API_KEY", values.get("MOONSHOT_API_KEY", "")).strip(),
            "model": values.get("AI_MODEL", values.get("KIMI_MODEL", "")).strip(),
        }

    @staticmethod
    def _validated_config(provider: str, base_url: str, api_key: str, model: str) -> dict[str, str]:
        config = {
            "provider": provider.strip(),
            "base_url": normalize_base_url(base_url),
            "api_key": api_key.strip(),
            "model": model.strip(),
        }
        if not config["provider"] or len(config["provider"]) > 50:
            raise ValueError("服务商名称不能为空且不能超过 50 个字符")
        if not config["model"] or len(config["model"]) > 120:
            raise ValueError("模型名不能为空且不能超过 120 个字符")
        if not config["api_key"]:
            raise ValueError("API Key 不能为空")
        if any("\n" in value or "\r" in value for value in config.values()):
            raise ValueError("模型配置不能包含换行符")
        return config

    def config(self) -> dict[str, Any]:
        config = self._config()
        configured = all(config.values())
        return {
            "provider": config["provider"],
            "base_url": config["base_url"],
            "model": config["model"],
            "configured": configured,
            "has_api_key": bool(config["api_key"]),
        }

    def save_config(self, provider: str, base_url: str, api_key: str, model: str) -> dict[str, Any]:
        api_key = api_key.strip() or self._config()["api_key"]
        config = self._validated_config(provider, base_url, api_key, model)
        write_env(
            self.config_path,
            {
                "AI_PROVIDER": config["provider"],
                "AI_BASE_URL": config["base_url"],
                "AI_API_KEY": config["api_key"],
                "AI_MODEL": config["model"],
            },
        )
        self._client = None
        self._client_signature = None
        self._cache.clear()
        return self.config()

    @staticmethod
    def _request(config: Mapping[str, str], messages: list[dict[str, str]], max_tokens: int) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": config["model"],
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if config["model"].lower().startswith("kimi-"):
            request["extra_body"] = {"thinking": {"type": "disabled"}}
        return request

    @staticmethod
    def _new_client(config: Mapping[str, str]):
        from openai import OpenAI

        return OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
            timeout=30.0,
            max_retries=0,
        )

    def test_config(
        self,
        provider: str | None = None,
        base_url: str | None = None,
        api_key: str = "",
        model: str | None = None,
    ) -> dict[str, Any]:
        current = self._config()
        config = self._validated_config(
            provider if provider is not None else current["provider"],
            base_url if base_url is not None else current["base_url"],
            api_key or current["api_key"],
            model if model is not None else current["model"],
        )
        client = self._new_client(config)
        try:
            client.chat.completions.create(
                **self._request(
                    config,
                    [{"role": "user", "content": "只回复 OK"}],
                    max_tokens=8,
                )
            )
        except Exception as exc:
            message = (str(exc) or type(exc).__name__).replace(config["api_key"], "***")
            raise RuntimeError(message) from exc
        return {"ok": True, "provider": config["provider"], "model": config["model"]}

    def _provider_complete(self, messages: list[dict[str, str]]) -> str:
        config = self._validated_config(**self._config())
        signature = (config["base_url"], config["api_key"])
        if self._client is None or self._client_signature != signature:
            self._client = self._new_client(config)
            self._client_signature = signature
        response = self._client.chat.completions.create(
            **self._request(config, messages, max_tokens=120)
        )
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
                "reason": f"AI 生成失败：{type(exc).__name__}",
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
