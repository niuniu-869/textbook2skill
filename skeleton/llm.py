"""LLM 客户端抽象（最小骨架）

设计原则:
- 不为不同 provider 写大量分支，统一 OpenAI-compatible API
- 不传 max_tokens / temperature（reasoning 模型陷阱，V0 踩过）
- 失败重试 1 次，再失败抛异常让上层决策

支持 provider:
- deepseek (默认): https://api.deepseek.com  model=deepseek-v4-flash
- anthropic: https://api.anthropic.com (要走另一套接口，未实现)
- openai-compatible 第三方: 透传 base_url + key

使用:
    client = LLMClient.from_env()  # 读 DEEPSEEK_KEY 等
    text = client.chat([{"role": "user", "content": "..."}])
"""
import os
import time
from dataclasses import dataclass
import requests


@dataclass
class LLMClient:
    base_url: str
    api_key: str
    model: str
    timeout: int = 600

    @classmethod
    def from_env(cls, provider: str = "deepseek") -> "LLMClient":
        """从环境变量构造。Provider 决定默认 base_url / model / env key 名"""
        configs = {
            "deepseek": {
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4-flash",
                "env_key": "DEEPSEEK_KEY",
            },
            "openai": {
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
                "env_key": "OPENAI_API_KEY",
            },
            # 用户也可以用任何 OpenAI-compatible 第三方
        }
        if provider not in configs:
            raise ValueError(f"Unknown provider {provider}, supported: {list(configs)}")
        cfg = configs[provider]
        key = os.environ.get(cfg["env_key"], "")
        if not key:
            raise RuntimeError(
                f"{cfg['env_key']} 未设置。请获取 key 后:\n"
                f"  export {cfg['env_key']}=your-key"
            )
        return cls(base_url=cfg["base_url"], api_key=key, model=cfg["model"])

    def chat(self, messages: list, retries: int = 1) -> str:
        """发请求，返回 content 字符串。
        ⚠️ 不传 max_tokens / temperature（reasoning 模型陷阱）
        """
        body = {"model": self.model, "messages": messages}
        last_err = None
        for attempt in range(retries + 1):
            try:
                r = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=self.timeout,
                )
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
                if not content or not content.strip():
                    raise RuntimeError(
                        "LLM returned empty content. "
                        "Reasoning models may consume budget silently — "
                        "check that you're NOT setting max_tokens."
                    )
                return content
            except Exception as e:
                last_err = e
                if attempt < retries:
                    time.sleep(2)
                    continue
                raise
        raise last_err  # unreachable


def chat_concurrent(
    client: LLMClient,
    prompts: list,
    max_workers: int = 8,
) -> list:
    """并发调用 LLM，返回与输入等长的结果列表。
    单个失败不阻断其他，失败位置返回 None
    """
    from concurrent.futures import ThreadPoolExecutor
    results = [None] * len(prompts)

    def worker(idx_msg):
        idx, msgs = idx_msg
        try:
            return idx, client.chat(msgs)
        except Exception as e:
            print(f"[llm] prompt {idx} failed: {e}", flush=True)
            return idx, None

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for idx, result in ex.map(worker, [(i, p) for i, p in enumerate(prompts)]):
            results[idx] = result
    return results
