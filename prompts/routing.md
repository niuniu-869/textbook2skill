# 章节路由 prompt 模板（top-k 版本）

`bench.py` 的 `route_chapter_topk()` 用这个模板。`{topic_lines}` / `{question}` / `{topic}` / `{k}` 会被替换。

## prompt（直接复制使用）

```
你是题目路由器。读用户的题目/问题，从下方章节中选**最相关的 1-{k} 个**章节文件。

章节主题关键词：
{topic_lines}

**重要规则**:
1. 大多数题目只需要 1 个章节。当题目跨章或不确定时，最多选 2 个。
2. **过宽章节（如总论 / 概述类）只在题目问"领域整体框架"时选**，不要因为关键词宽泛就选它。
3. 优先匹配具体的术语 / 公式名 / 方法名，而不是抽象概念。

题目/问题：{question}
（可选）考点：{topic}

输出格式：每行一个章节文件名（含 `.md` 后缀），按相关性降序，最多 {k} 行。**不要任何其他文字 / 解释 / markdown 格式。**

示例输出（选 1 章）：
03-第3章_本量利分析.md

示例输出（跨章问题，选 2 章）：
06-第6章_长期投资决策.md
11-第11章_战略业绩评价.md
```

## 关键设计点

1. **Top-k 而不是 top-1** — 跨章节问题或低置信度时多选 1 个
2. **不写死"ban 第 N 章"** — 改成"过宽章节降权"通用规则（codex 反馈：硬编码第 1 章 ban 是 V0 hack）
3. **明确输出格式** — 防止 LLM 加解释
4. **示例双 case** — 教 LLM 何时选 1 何时选 2

## fallback 策略

`bench.py` 的 `route_chapter_topk()` 解析 LLM 输出后做匹配：

```python
candidates = []
for line in resp.strip().split("\n")[:k]:
    line = line.strip().strip("`").strip("- ").strip()
    if not line:
        continue
    # Layer 1: 精确匹配
    if line in chapter_topics:
        candidates.append(line)
        continue
    # Layer 2: 模糊匹配（文件名相互包含）
    for name in chapter_topics:
        if name in line or line.replace(".md", "") in name:
            candidates.append(name)
            break
return candidates[:k]
```

如果 0 个章节命中：
- `answer_with_skill()` 会传空 `chapter_content`，system prompt 触发 "本章未覆盖" fallback

## 章节关键词清单从哪来

`bench.py` 的 `_parse_chapter_topics()` 解析 SKILL.md 的章节速查表：

```
| 第1章 管理会计概述 | 企业使命、企业目标、... | `chapters/01-...md` |
```

提取出 `{文件名: 关键词字符串}` 字典传给 routing prompt。

## 路由准确率监控

`bench.py` 的 `build_report()` 算路由准确率：把每题的 `expected_chapter`（从题目元数据 `chapter` 字段）和 `actual_chapter`（LLM 选的）比，比章节编号前缀。

V0 实测目标：**≥ 90%**。

低于 90% 时排查：
- 关键词不准 → 重新提取关键词（assemble.py 的 `extract_keywords()` 扩展来源）
- 跨章节题目被路到错章 → 把 k 调到 3，或在 prompt 加跨章 hint
- 过宽章节被滥选 → routing prompt 的"过宽章节降权"规则强化
