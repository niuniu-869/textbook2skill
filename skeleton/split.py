"""章节切分（多策略 chain，最小骨架）

Input:  full markdown (str)
Output: chapters.json [{idx, title, content, source_strategy, num?}]

策略链（按可靠性降序，第一个成功的就用）:
1. **TOC-first**: 找 "# 目录" 区域提取章节列表 → 在正文里 grep 章节标题位置
2. **H1 + size 启发**: 所有 H1 按字符量分组，长的就是章节
3. **语义锚点**: 找"学习目标 + 通过本章学习"等固定开头（V0 策略，不通用）
4. **LLM 兜底**: 让 LLM 看 markdown 头 + TOC 提议章节起点（未实现，留接口）

Codex 反馈过：单一锚点过拟合 V0 教材，必须 strategy chain。
"""
import re
import json
import sys
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class Chapter:
    idx: int
    title: str
    content: str
    source_strategy: str
    num: str | None = None  # 章节号（如 "3" 或 "三"）


# ---------- TOC 提取（多本教材通用）----------

def extract_toc(markdown: str) -> list[str]:
    """从 markdown 开头的 # 目录 / TOC 区域提取章节列表"""
    # 找目录起点
    toc_anchors = [r"^# 目录\s*$", r"^# Contents?\s*$", r"^# Table of Contents\s*$"]
    region_start = None
    for anchor in toc_anchors:
        m = re.search(anchor, markdown, re.MULTILINE | re.IGNORECASE)
        if m:
            region_start = m.end()
            break
    if region_start is None:
        return []

    chapters = []
    # 从 TOC 起点扫到第一个非 TOC 章节标题（即正文）
    for line in markdown[region_start:].split("\n")[:200]:  # 限 200 行避免漂移
        line = line.strip()
        m = re.match(
            r"^#+\s*第([一二三四五六七八九十百零\d]+)章[ \t]*(.*)$|"
            r"^#+\s*Chapter\s*(\d+)[ \t]*(.+)$",
            line,
            re.IGNORECASE,
        )
        if not m:
            continue
        num = m.group(1) or m.group(3)
        title = (m.group(2) or m.group(4) or "").strip()
        # TOC 条目带页码标志（$、→、⇒、行尾纯数字）
        if _is_toc_line(title):
            clean = _clean_toc_title(title)
            chapters.append(f"第{num}章 {clean}")
        elif chapters:
            # 进入正文了
            break
    return chapters


def _is_toc_line(rest: str) -> bool:
    rest = rest.strip()
    if not rest:
        return False
    if any(s in rest for s in ["$", "→", "⇒", "\\Rightarrow", "\\rightarrow"]):
        return True
    parts = rest.split()
    if parts and parts[-1].isdigit():
        return True
    return False


def _clean_toc_title(rest: str) -> str:
    rest = re.sub(r"\$[^$]*\$", "", rest).strip()
    rest = re.sub(r"\s+\d+$", "", rest).strip()
    return rest


# ---------- Strategy 1: TOC-first ----------

def split_by_toc(markdown: str) -> list[Chapter]:
    """用 TOC 章节标题在正文里 grep 起点位置"""
    toc = extract_toc(markdown)
    if not toc:
        return []

    chapters = []
    positions = []
    for entry in toc:
        m = re.match(r"^第([^章]+)章\s*(.+)$", entry)
        if not m:
            continue
        num, title = m.group(1), m.group(2)
        # 在正文里找这个标题（不带页码标志）
        # 多种格式: "# 第N章\n# 标题"、"# 第N章 标题"
        patterns = [
            rf"^#\s*第{re.escape(num)}章\s*\n\s*#\s*{re.escape(title[:10])}",
            rf"^#\s*第{re.escape(num)}章\s+{re.escape(title[:10])}",
            rf"^#\s*{re.escape(title[:15])}\s*$",
        ]
        found_pos = None
        for p in patterns:
            for m in re.finditer(p, markdown, re.MULTILINE):
                # 跳过 TOC 区（前 5%）
                if m.start() > len(markdown) * 0.05:
                    found_pos = m.start()
                    break
            if found_pos is not None:
                break
        if found_pos is not None:
            positions.append((found_pos, num, title))

    if not positions:
        return []

    positions.sort()
    for i, (start, num, title) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(markdown)
        chapters.append(Chapter(
            idx=i + 1,
            title=f"第{num}章 {title}",
            content=markdown[start:end].strip(),
            source_strategy="toc-first",
            num=num,
        ))
    return chapters


# ---------- Strategy 2: H1 + size 启发 ----------

def split_by_h1_size(markdown: str, min_chars: int = 3000) -> list[Chapter]:
    """所有 H1 标题做切分，过滤过短的（< min_chars 字符的不算章节）"""
    h1_positions = [(m.start(), m.group(1).strip())
                    for m in re.finditer(r"^#\s+(.+?)$", markdown, re.MULTILINE)]
    if not h1_positions:
        return []

    candidates = []
    for i, (pos, title) in enumerate(h1_positions):
        next_pos = h1_positions[i + 1][0] if i + 1 < len(h1_positions) else len(markdown)
        size = next_pos - pos
        if size >= min_chars:
            candidates.append((pos, title, size))

    if not candidates:
        return []

    chapters = []
    for i, (pos, title, _) in enumerate(candidates):
        end = candidates[i + 1][0] if i + 1 < len(candidates) else len(markdown)
        chapters.append(Chapter(
            idx=i + 1,
            title=title,
            content=markdown[pos:end].strip(),
            source_strategy="h1-size",
        ))
    return chapters


# ---------- Strategy 3: 语义锚点（V0 策略）----------

# 多种语言的"章节开头"标志短语
ANCHOR_PHRASES = [
    r"^# 学习目标\s*\n+\s*通过本章学习",
    r"^# Learning Objectives\s*\n+\s*After (?:reading|studying)",
    r"^# 本章导读\s*\n",
]


def split_by_anchor(markdown: str) -> list[Chapter]:
    anchors = []
    for pattern in ANCHOR_PHRASES:
        for m in re.finditer(pattern, markdown, re.MULTILINE | re.IGNORECASE):
            anchors.append(m.start())
    if not anchors:
        return []
    anchors.sort()

    # 对每个锚点，向前找最近 H1 作为章节起点
    chapters = []
    for anchor_pos in anchors:
        before = markdown[:anchor_pos]
        # 倒着找最近 H1
        last_h1 = None
        for m in re.finditer(r"^#\s+(.+)$", before, re.MULTILINE):
            last_h1 = (m.start(), m.group(1).strip())
        if last_h1 is None:
            continue
        chapters.append(last_h1)

    # 去重 + 排序
    chapters = sorted(set(chapters))
    if not chapters:
        return []

    result = []
    for i, (pos, title) in enumerate(chapters):
        end = chapters[i + 1][0] if i + 1 < len(chapters) else len(markdown)
        result.append(Chapter(
            idx=i + 1,
            title=title,
            content=markdown[pos:end].strip(),
            source_strategy="semantic-anchor",
        ))
    return result


# ---------- Strategy 4: LLM 兜底 ----------

def split_by_llm(markdown: str, llm_client) -> list[Chapter]:
    """让 LLM 看 markdown 头 + TOC 提议章节标题列表，再 grep 位置。
    未完整实现 — 留接口让 Claude 按需扩展。
    """
    raise NotImplementedError(
        "LLM fallback split: TODO — 让 LLM 看 markdown[:5000] + extract_toc(),"
        "提议每章首行 markdown 字符串，再 grep 在原文位置"
    )


# ---------- Strategy chain ----------

def split_chapters(markdown: str, llm_client=None) -> list[Chapter]:
    """按 strategy chain 切章。第一个产出 ≥3 章的策略胜出"""
    strategies = [
        ("toc-first", split_by_toc),
        ("h1-size", split_by_h1_size),
        ("semantic-anchor", split_by_anchor),
    ]
    for name, fn in strategies:
        try:
            result = fn(markdown)
        except Exception as e:
            print(f"[split] {name} failed: {e}", flush=True)
            continue
        if len(result) >= 3:
            print(f"[split] strategy={name} 识别 {len(result)} 章", flush=True)
            return result
        print(f"[split] strategy={name} 只识别 {len(result)} 章，尝试下一个", flush=True)

    # 全部失败 → LLM 兜底（如果有 client）
    if llm_client is not None:
        return split_by_llm(markdown, llm_client)

    raise RuntimeError(
        "全部 split 策略失败。建议:\n"
        "1. 人眼看 markdown 头部，确认章节格式\n"
        "2. 在 ANCHOR_PHRASES 加新锚点\n"
        "3. 提供 llm_client 走 LLM 兜底"
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: split.py <input.md> <output.json>", file=sys.stderr)
        sys.exit(1)
    md = Path(sys.argv[1]).read_text(encoding="utf-8")
    chapters = split_chapters(md)
    out = [asdict(c) for c in chapters]
    Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[split] 写入 {len(chapters)} 章到 {sys.argv[2]}", flush=True)
