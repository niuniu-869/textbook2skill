"""LLM 抽取章节内容（最小骨架）

Input:  chapters.json + LLM client
Output: extracted/<idx>-<title>.md，每章一个 markdown 文件

⚠️ 关键约束:
- LLM 调用绝不传 max_tokens / temperature（reasoning 模型陷阱）
- 并发跑（DeepSeek 支持高并发，串行差 10x+）
- 抽取 prompt 模板在 prompts/extraction.md，按需读取（这里只引用）

V0 实测 prompt 关键点:
- 明确 "写给机器看不是给学生看"
- 含反例（❌ 不要写"本章主要介绍"）
- 强制结构: 核心概念 / 公式 / 方法 / 例题 / 易混点 / 关联
- 数字、公式 100% 准确，OCR 错乱标 [OCR错乱]
"""
import json
import re
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from llm import LLMClient


def load_extraction_prompt(prompt_dir: Path) -> str:
    """从 prompts/extraction.md 加载 prompt 模板（含 {chapter_text} 占位符）"""
    prompt_file = prompt_dir / "extraction.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"找不到 extraction prompt: {prompt_file}")
    raw = prompt_file.read_text(encoding="utf-8")
    # 提取 ``` 代码块里的实际 prompt（如果用户用代码块包裹了模板）
    m = re.search(r"```\s*\n(.+?)\n```", raw, re.DOTALL)
    return m.group(1) if m else raw


def extract_one_chapter(client: LLMClient, prompt_template: str, chapter: dict) -> str:
    """处理单章。返回抽取后的 markdown"""
    text = chapter["content"]
    # 截断超长章节（节省 token）
    if len(text) > 30000:
        text = text[:30000] + "\n[...章节后段省略...]"
    prompt = prompt_template.replace("{chapter_text}", text)
    return client.chat([{"role": "user", "content": prompt}])


def extract_all(
    chapters: list[dict],
    output_dir: Path,
    client: LLMClient,
    prompt_dir: Path,
    max_workers: int = 11,
) -> list[Path]:
    """并发抽取所有章节，返回输出文件路径列表"""
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_template = load_extraction_prompt(prompt_dir)

    def worker(chapter):
        idx = chapter["idx"]
        title = chapter["title"]
        print(f"[extract] {idx}: {title[:30]}...", flush=True)
        try:
            result = extract_one_chapter(client, prompt_template, chapter)
        except Exception as e:
            print(f"[extract] {idx} 失败: {e}", flush=True)
            result = f"# {title}\n\n[抽取失败: {e}]\n"
        # 文件名安全化
        safe_title = re.sub(r"[^\w一-鿿\-]", "_", title)[:60]
        filename = f"{idx:02d}-{safe_title}.md"
        path = output_dir / filename
        path.write_text(result, encoding="utf-8")
        return path

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        results = list(ex.map(worker, chapters))
    return results


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            "Usage: extract.py <chapters.json> <output_dir> <prompt_dir> [provider]",
            file=sys.stderr,
        )
        sys.exit(1)
    chapters = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    output_dir = Path(sys.argv[2])
    prompt_dir = Path(sys.argv[3])
    provider = sys.argv[4] if len(sys.argv) > 4 else "deepseek"

    client = LLMClient.from_env(provider)
    paths = extract_all(chapters, output_dir, client, prompt_dir)
    print(f"\n[main] 抽取完成 {len(paths)} 章 → {output_dir}", flush=True)
