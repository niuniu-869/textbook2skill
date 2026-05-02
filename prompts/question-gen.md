# Benchmark 出题 prompt 模板

`bench.py` 的 `gen_questions_one_chapter()` 用这个模板。`{count}` / `{distribution}` / `{chapter_prefix}` / `{chapter_text}` 会被替换。

## prompt（直接复制使用）

```
你是一位资深 {领域} 教师，正在为期末考试出题。下面是教材某一章的原文（OCR 输出，可能有少量识别错误）。

请基于这一章的核心内容，生成 {count} 道**原创题**（绝对不能与原书例题相同，但要测试相同的考点）。题目按以下要求生成：

要求:
1. **{count} 道题难度分布**: {distribution}
2. **题型混合**: 至少包含 1 道选择题 + 1 道填空题
3. **绝对原创**: 不要复制教材例题，但可以在相同主题下设计新数字、新场景
4. **答案明确无歧义**: 选择题只有一个正确选项；填空题答案是确定的术语/数字
5. **聚焦教材独有口径**: 优先考查教材里的特殊定义、特定公式、术语原貌

输出严格 JSON 数组（不要 markdown 代码块包裹）：
[
  {
    "id": "{chapter_prefix}-1",
    "type": "choice",         // "choice" 或 "fill"
    "difficulty": "easy",      // "easy" / "medium" / "hard"
    "topic": "本量利分析-贡献毛益概念",
    "question": "题干内容",
    "options": {
      "A": "选项 A", "B": "选项 B", "C": "选项 C", "D": "选项 D"
    },
    "answer": "B",              // 选择题填字母；填空题填答案文本/数字
    "answer_aliases": ["可接受的等价答案1", "等价答案2"],
    "rationale": "考查本量利公式中的贡献毛益定义"
  }
]

特别注意:
- 选择题的 4 个选项要有迷惑性（错误选项不能太离谱）
- 填空题的 answer_aliases 要包含合理的等价表达（如"贡献毛益"和"边际贡献"）
- 数字答案的 aliases 包含不同精度（如 18.75% / 18.8% / 0.1875）
- 题目编号 id 用 {chapter_prefix}-1、{chapter_prefix}-2...

教材原文如下：

{chapter_text}
```

## 难度分布规则（pipeline.py 自动计算）

```python
def difficulty_distribution(count: int) -> str:
    if count == 1: return "1 中等"
    elif count == 2: return "1 简单 + 1 中等"
    elif count == 3: return "1 简单 + 1 中等 + 1 困难"
    elif count == 4: return "1 简单 + 2 中等 + 1 困难"
```

## 章节题数分配

`pipeline.py` 的 `_allocate()` 按章节 token 量比例分。也可以手动给：

```python
allocation = {
    "01-第1章": 2,   # 总论
    "02-第2章": 4,   # 公式密集
    "03-第3章": 4,   # 核心
    "04-第4章": 2,
    "05-第5章": 3,
    "06-第6章": 4,   # 长投决策
    "07-第7章": 1,   # 概念章节
    "08-第8章": 2,
    "09-第9章": 3,
    "10-第10章": 2,
    "11-第11章": 3,
}
```

总数固定 30。每章数量根据教材实际深度调整。

## 出题失败的 fallback

`bench.py` 的 `_parse_json_array()` 处理 LLM 偶尔输出格式错的 JSON：

```python
def _parse_json_array(text: str) -> list:
    text = text.strip()
    # 去 markdown 代码块包裹
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    # 找第一个 [ 到最后一个 ]
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)
```

如果还失败 → 这章 0 题，benchmark 总题数变 < 30（可接受，会在报告里看出来）。

## 题目质量验证

出完后人/Claude 抽查 3-5 道：
- 题干是否清晰
- 答案是否唯一
- 是否真的"原创"（不是教材例题原文）
- 难度标注是否准确

不合格的题手动删除或重新生成。

## 并发出题

`gen_questions()` 用 `ThreadPoolExecutor(max_workers=11)`，11 章并发，~30 秒拿到 30 题。

## V0 实测样本（参考分布）

在 330 页中文管理会计教材上跑过的 30 题分布：
- easy 10 / medium 15 / hard 6
- choice 16 / fill 15

LLM 自动按 `difficulty_distribution()` 规则会接近这个比例。如果实际跑出来偏离很多，检查 prompt 里的"难度分布"约束。
