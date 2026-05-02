"""组装最终 skill 目录（最小骨架）

Input:  extracted/<idx>-<title>.md 文件们 + 元数据
Output: skill/{SKILL.md, chapters/*.md}

设计要点（codex review 修订后）:
- 关键词来源扩展: 不只是 ## 核心概念，还包括公式名、方法名、例题 topic
- description + when_to_use 严格控制在 1500 字符内（< 1536 上限）
- 章节速查表用 markdown 表格（V0 实测路由准确率高）
"""
import json
import re
import sys
from pathlib import Path


SKILL_MD_TEMPLATE = """---
name: {skill_name}
description: {description}
when_to_use: {when_to_use}
---

# {book_title}

本 skill 由教材《{book_title}》自动炼化为 Claude 可消费的领域知识包。**不是给学生看的学习指南，是给 Claude 用来准确回答用户问题的领域参考。**

## 使用流程（必读）

1. 收到用户问题时，先看下方"章节速查表"，找最相关的 1-2 个章节
2. 用 Read 工具加载 `chapters/<filename>.md`
3. 基于章节内容回答；若问题跨章，按相关性顺序最多加载 2 个
4. 章节文件结构：核心概念 / 公式与计算口径 / 方法流程 / 例题 / 易混点 / 关联
5. **回答时直接引用章节内容，不要说"根据参考资料"或"教材中提到"**

## 章节速查表

| 章节 | 关键词（精确命中） | 文件 |
|------|------|------|
{chapter_table}

## 反例

❌ 用户问 "X" → 把所有章节全加载（浪费 context）
❌ 用户问具体术语 → 不加载任何章节直接靠记忆（漏教材独有口径）
✅ 用户问 "X" → 只加载第 N 章（最相关那一章）
"""


def extract_keywords(chapter_md: str, max_kw: int = 8) -> list[str]:
    """从抽取后的章节 markdown 提关键词。
    源:
    - ## 核心概念 的 **术语**: 定义
    - ## 公式与计算口径 的 **公式名**:
    - ## 例题 的 ### 例 X.M: topic
    Codex 反馈过：只取核心概念会丢公式名 / 例题 topic / 别名
    """
    kws = []

    # 1. 核心概念 bullet
    m = re.search(r"##\s*核心概念\s*\n(.+?)(?=\n##|\Z)", chapter_md, re.DOTALL)
    if m:
        for line in m.group(1).split("\n"):
            km = re.match(r"^\s*-\s*\*\*([^*]+?)\*\*\s*[:：]", line)
            if km:
                kws.append(km.group(1).strip())

    # 2. 公式名
    m = re.search(r"##\s*公式与计算口径\s*\n(.+?)(?=\n##|\Z)", chapter_md, re.DOTALL)
    if m:
        for line in m.group(1).split("\n"):
            km = re.match(r"^\s*-\s*\*\*([^*]+?)\*\*\s*[:：]", line)
            if km:
                kws.append(km.group(1).strip())

    # 3. 例题 topic
    for m in re.finditer(r"^###\s*例[^:]+[:：]\s*(.+)$", chapter_md, re.MULTILINE):
        topic = m.group(1).strip()
        # 截短
        if len(topic) > 20:
            topic = topic[:20]
        kws.append(topic)

    # 去重保序
    seen = set()
    unique = []
    for k in kws:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    return unique[:max_kw]


def build_description(book_title: str, chapter_topics: list[str], all_keywords: list[str]) -> tuple[str, str]:
    """构造 description + when_to_use，确保总长 ≤ 1500 字符"""
    topic_summary = "、".join(chapter_topics[:6])
    if len(chapter_topics) > 6:
        topic_summary += f"等 {len(chapter_topics)} 章"

    description = (
        f"《{book_title}》专家技能 — 覆盖{topic_summary}。"
        f"用户问及{('、'.join(all_keywords[:8]) if all_keywords else '相关概念')}时优先使用。"
    )

    when_to_use_kws = "、".join(all_keywords[:15]) if all_keywords else "相关专题"
    when_to_use = f"用户问及以下任一概念时：{when_to_use_kws}"

    # 总长截断
    total = len(description) + len(when_to_use)
    if total > 1500:
        # 缩减 when_to_use 关键词数
        budget = 1500 - len(description) - 5
        when_to_use = when_to_use[:budget] + "..."

    return description, when_to_use


def assemble(
    extracted_dir: Path,
    output_dir: Path,
    skill_name: str,
    book_title: str,
) -> Path:
    """组装最终 skill 目录"""
    output_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir = output_dir / "chapters"
    chapters_dir.mkdir(exist_ok=True)

    chapter_files = sorted(extracted_dir.glob("*.md"))
    if not chapter_files:
        raise RuntimeError(f"未找到抽取后的章节文件 in {extracted_dir}")

    chapter_rows = []
    chapter_topics = []
    all_keywords = []
    for src in chapter_files:
        content = src.read_text(encoding="utf-8")
        # 从首行提取标题（# Xxx）
        first = content.split("\n", 1)[0].lstrip("#").strip()
        # 提取章节主题（"第 N 章 主题" → "主题"）
        topic_m = re.match(r"^第[^章]+章\s+(.+)$", first)
        topic = topic_m.group(1) if topic_m else first
        chapter_topics.append(topic)

        keywords = extract_keywords(content)
        all_keywords.extend(keywords)
        keyword_str = "、".join(keywords[:5]) if keywords else "(待补)"

        # 写章节文件到 skill/chapters/
        dest = chapters_dir / src.name
        dest.write_text(content, encoding="utf-8")
        chapter_rows.append(f"| {first} | {keyword_str} | `chapters/{src.name}` |")

    description, when_to_use = build_description(book_title, chapter_topics, all_keywords)

    skill_md = SKILL_MD_TEMPLATE.format(
        skill_name=skill_name,
        description=description,
        when_to_use=when_to_use,
        book_title=book_title,
        chapter_table="\n".join(chapter_rows),
    )
    skill_md_path = output_dir / "SKILL.md"
    skill_md_path.write_text(skill_md, encoding="utf-8")

    print(f"[assemble] {len(chapter_files)} 章 → {output_dir}", flush=True)
    print(f"[assemble] SKILL.md {len(skill_md)} 字符", flush=True)
    print(f"[assemble] description+when_to_use {len(description)+len(when_to_use)} 字符 (上限 1536)", flush=True)
    print(f"[assemble] 关键词样例: {all_keywords[:10]}", flush=True)
    return output_dir


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(
            "Usage: assemble.py <extracted_dir> <output_dir> <skill_name> <book_title>",
            file=sys.stderr,
        )
        sys.exit(1)
    extracted = Path(sys.argv[1])
    output = Path(sys.argv[2])
    name = sys.argv[3]
    title = sys.argv[4]
    assemble(extracted, output, name, title)
