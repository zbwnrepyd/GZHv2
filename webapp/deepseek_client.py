import json
import time
import requests
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """加载 prompt 模板文件"""
    prompt_path = PROMPTS_DIR / f"{name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def call_deepseek(
    api_key: str,
    system_prompt: str,
    user_message: str,
    model: str = "deepseek-v4-pro",
    temperature: float = 0.1,
    max_tokens: int = 8192,
    timeout: int = 120,
    max_retries: int = 3,
) -> str:
    """调用 DeepSeek API（OpenAI 兼容格式），含自动重试"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers=headers,
                json=body,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout as e:
            last_error = e
            wait = (attempt + 1) * 10
            time.sleep(wait)
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < max_retries - 1:
                wait = 2**attempt
                time.sleep(wait)

    raise RuntimeError(
        f"DeepSeek API 调用失败（重试 {max_retries} 次）: {last_error}"
    )


def call_deepseek_with_prompt_file(
    api_key: str,
    prompt_name: str,
    user_message: str,
    model: str = "deepseek-v4-pro",
    temperature: float = 0.1,
    **kwargs,
) -> str:
    """从 prompt 文件加载系统提示词，调用 DeepSeek"""
    system_prompt = load_prompt(prompt_name)
    return call_deepseek(
        api_key, system_prompt, user_message, model=model, temperature=temperature, **kwargs
    )
