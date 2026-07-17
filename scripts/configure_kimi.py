from __future__ import annotations

import argparse
import re
from pathlib import Path


KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{5,}")
MODEL_PREFERENCE = (
    "kimi-k2.6",
    "kimi-k2.5",
    "moonshot-v1-auto",
    "moonshot-v1-32k",
    "moonshot-v1-8k",
)


def extract_keys(text: str) -> list[str]:
    return list(dict.fromkeys(KEY_PATTERN.findall(text)))


def choose_model(model_ids: list[str]) -> str:
    available = set(model_ids)
    for model in MODEL_PREFERENCE:
        if model in available:
            return model
    general = next((model for model in model_ids if "code" not in model.lower()), "")
    if not general:
        raise RuntimeError("没有可用的通用对话模型")
    return general


def write_env(path: Path, key: str, model: str) -> None:
    content = (
        "AI_PROVIDER=Kimi\n"
        "AI_BASE_URL=https://api.moonshot.cn/v1\n"
        f"AI_API_KEY={key}\n"
        f"AI_MODEL={model}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def verify_key(key: str) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=key,
        base_url="https://api.moonshot.cn/v1",
        timeout=20.0,
        max_retries=0,
    )
    model_ids = [model.id for model in client.models.list().data]
    model = choose_model(model_ids)
    request = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "只回复一条自然、简短的中文招聘消息，不要解释。",
            },
            {"role": "user", "content": "候选人问：还招人吗？"},
        ],
        "max_tokens": 80,
    }
    if model in {"kimi-k2.6", "kimi-k2.5"}:
        request["extra_body"] = {"thinking": {"type": "disabled"}}
    response = client.chat.completions.create(**request)
    if not (response.choices and (response.choices[0].message.content or "").strip()):
        raise RuntimeError("模型没有返回文本")
    return model


def error_label(exc: Exception) -> str:
    name = type(exc).__name__
    if name == "AuthenticationError":
        return "认证失败"
    if name == "RateLimitError":
        return "限流或余额不足"
    if name in {"APIConnectionError", "APITimeoutError"}:
        return "网络连接失败"
    return "接口调用失败"


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 Kimi Key 并生成本机配置")
    parser.add_argument(
        "key_file",
        nargs="?",
        type=Path,
        default=Path(r"C:\Users\81591\Desktop\kimi-keys.txt"),
    )
    parser.add_argument("--env", type=Path, default=Path(".env"))
    args = parser.parse_args()

    keys = extract_keys(args.key_file.read_text(encoding="utf-8-sig"))
    if not keys:
        print("未找到 Kimi Key")
        return 2

    for index, key in enumerate(keys, start=1):
        try:
            model = verify_key(key)
        except Exception as exc:
            print(f"Key #{index}: 不可用（{error_label(exc)}）")
            continue
        write_env(args.env, key, model)
        print(f"Key #{index}: 可用，已配置模型 {model}")
        return 0

    print("没有可用的 Kimi Key")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
