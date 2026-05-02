# Step 7: Benchmark（必跑）

**核心原则**：没有 benchmark 就没有 skill。任何 skill 在交付前必须跑 WITH/WITHOUT 对比，否则交付的是幻觉。

## 为什么必跑

- LLM baseline 比想象中强很多 — V0 实测管理会计 DeepSeek 裸答 84%
- skill 在主流学科可能只加 5-10%，在冷门领域可能加 30%+
- **不跑 benchmark 你不知道这个 skill 是不是在装样子**
- 用户付出时间装了 skill，你欠他一个"是否值得"的答案

## Benchmark 流程

```
[a] 出题：用 LLM 读全书 markdown，每章按 token 量比例分配题数，总 30 题
[b] 跑测：每题两次 LLM 调用 — WITH skill (路由→加载章节→回答) vs WITHOUT skill (裸问)
[c] 评分：MCQ 提取字母对比，填空数字±2% 或文本模糊匹配
[d] McNemar test 算 p-value（不是只看 +Δ%）
[e] 出报告：分层指标 + 显著性 + "是否可交付"判断
```

## 命令

```bash
python3 ${SKILL_DIR}/skeleton/bench.py \
  <skill_dir> \
  <questions.json> \
  ${SKILL_DIR}/prompts \
  [provider]   # 默认 deepseek
```

或通过 pipeline.py 自动跑（默认开）：
```bash
python3 pipeline.py --pdf ... --skill-name ...   # benchmark 默认跑
python3 pipeline.py ... --skip-bench             # 跳过（不推荐）
```

## I/O 契约

| 阶段 | 输入 | 输出 |
|------|------|------|
| 出题 | `chapters.json` + allocation dict | `benchmark-questions.json` |
| 跑测 + 评分 | `questions.json` + `skill_dir` | `benchmark.json`（每题完整结果） + `report.md`（人类可读） |

## 出题 prompt（详见 [prompts/question-gen.md](../prompts/question-gen.md)）

关键约束：
1. **必须原创** — 不能复制教材原题，但要测同样考点
2. **三档难度**：easy（概念） / medium（计算） / hard（综合应用）
3. **题型混合**：选择题 + 填空题（自动评分稳定）
4. **答案明确无歧义**
5. **优先考查教材独有口径** — skill 真能加分的场景

## WITH skill 的执行模式

`bench.py` 的 `answer_with_skill()` 走完整流程：
1. **routing (top-k)**: 让 LLM 看题目 + 章节关键词清单 → 选 top-k=2 章节文件名
2. **loading**: Read 选中章节
3. **answering**: system prompt 注入章节内容 + 题目 → 拿答案

**Codex 反馈过**：路由要 top-k 而不是 top-1（跨章节问题、低置信度场景）。

## WITHOUT skill 的执行模式

`answer_without_skill()` 裸问 LLM，只给 system prompt = "你是 X 领域专家，准确回答"。

## 评分（5 层 MCQ 提取 + 数字 ±2%）

`extract_mcq_letter()` 5 层 fallback：
1. 单字符
2. 尾部 200 字找 "答案是 X" / "选 X" 等模式
3. `**X**` / `\`X\`` 包裹
4. 全文最后一个出现的字母（最弱 fallback）

`grade()` 处理填空：数字 ±2% 容差 + 文本模糊包含匹配 + `answer_aliases` 等价。

## McNemar test（codex review 修订后）

V0 报 +6.5% 时 codex 指出"31 题 +2 题就 6.45%，基本是噪声"。修复：

`mcnemar_p_value(b, c)` 算单侧 p-value：
- `b` = WITH 对 + WITHOUT 错 数量
- `c` = WITH 错 + WITHOUT 对 数量
- p < 0.05 才能宣称"显著"

## 出报告

`build_report()` 输出 4 个维度：

```
============================================================
Benchmark Report (30 题)
============================================================
WITH    skill: 27/30 = 90.0%
WITHOUT skill: 25/30 = 83.3%
差距: +6.7%
McNemar test (one-sided): b=4, c=2, p=0.343
显著性: 不显著 (噪声内)

=== 按难度 ===
  easy  : WITH 9/10 (90%) | WITHOUT 9/10 (90%) | Δ +0%
  medium: WITH 13/15 (87%) | WITHOUT 13/15 (87%) | Δ +0%
  hard  : WITH 5/5 (100%) | WITHOUT 3/5 (60%) | Δ +40%

=== 按章节 ===
  01-第1章: WITH 2/2 | WITHOUT 2/2
  02-第2章: WITH 4/4 | WITHOUT 2/4    ← 公式密集，skill 真加分
  ...

=== 路由准确率 ===
  27/30 = 90%

=== 是否可交付 ===
  价值有限 — 差距不显著（可能是噪声），LLM baseline 已经强
```

## "是否可交付"判断逻辑

| McNemar p | 总差距 Δ | 判断 |
|-----------|----------|------|
| < 0.05 | ≥ +20% | 强烈推荐 |
| < 0.05 | ≥ +10% | 推荐 |
| < 0.05 | ≥ +5% | 有限提升 |
| ≥ 0.05 | > 0 | 价值有限（噪声内） |
| ≥ 0.05 | ≤ 0 | 不建议交付 |

**重要**：如果显示"价值有限"或"不建议交付"，**STOP 不要硬交付**。问用户：
- 要不要重新跑 prompt 优化？
- 要不要换更冷门的领域试？
- 还是接受 baseline LLM 自带就够，不装 skill？

## V0 实测案例参考

《高级管理会计理论与实务》30 题 benchmark：
- 总分：WITH 90.3% vs WITHOUT 83.9% = +6.5% (McNemar 不显著)
- Easy: 0% / Medium: +7% / **Hard: +17%**
- 第 2 章（成本计算系统，公式密集）: **+50%**（真信号）
- 其余 10 章: +0%
- 结论：skill 在难题 + 公式密集章节有显著价值，主流概念 baseline 自带

这是"主流学科"的典型表现。**冷门领域应该看到 +30% 以上的差距**。

## 失败模式

| 现象 | 原因 | 修复 |
|------|------|------|
| MCQ 提取大量 "(无法提取)" | LLM 答得太啰嗦 | 检查 extract_mcq_letter 5 层 fallback 是否生效 |
| WITH 和 WITHOUT 答案 100% 一致 | LLM 自带知识就够强 | 改用更冷门的题（教材独有口径） |
| WITH 反而比 WITHOUT 低 | 路由错章节 + 章节内容干扰 | 修路由 prompt + 检查 system prompt 没让 LLM "复述" |
| 出题 LLM 给的题太简单 | 出题 prompt 没强调"难度分布" | 加 "hard 题必须涉及多步推理或教材独有口径" |
| benchmark 跑 30 分钟没结束 | 串行调用 | 检查 max_workers，DeepSeek 应该并发 |
