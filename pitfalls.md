# V0 实测踩坑清单

按踩坑成本排序。每个坑都附"如何识别 + 修复"。这些都是 2026-05-02 在《高级管理会计理论与实务》上跑 V0 时实测发现的。

## P1 ⚡⚡⚡ DeepSeek-v4-flash 设了 max_tokens → content 为空

**现象**：API 调用没报错，但返回的 `choices[0].message.content` 是空字符串

**根因**：DeepSeek-v4-flash 是 reasoning 模型，内部 reasoning_tokens 占用预算，max_tokens 太小时 content 没空间

**修复**：API body **不要包含** `max_tokens` 和 `temperature` 字段，让 API 用默认值

**适用范围**：所有 reasoning 模型（DeepSeek-R1 系列、OpenAI o1/o3、Gemini Flash Thinking 等）

**Skeleton 已修复**：`skeleton/llm.py` 的 `chat()` 方法不传 max_tokens / temperature；遇到空 content 抛异常告诉用户排查

---

## P2 ⚡⚡⚡ 章节切分用 `# 第N章` 正则 → TOC 条目被误识别为章节

**现象**：识别章节数 = TOC 章数 × 2

**根因**：教材开头的 TOC 也是 `# 第N章 标题 $\Rightarrow 页码$` 格式，正则同时匹配 TOC 和正文

**修复**：先过滤 TOC 条目（含 `$` / `→` / `⇒` / 行尾纯数字），剩下的才是真章节

**Skeleton 已修复**：`skeleton/split.py` 的 `_is_toc_line()` 函数过滤 TOC 标志

---

## P3 ⚡⚡⚡ OCR 偶尔丢章节号 → 漏章

**现象**：第 N 章 OCR 后只有 `# 章节标题`，没有 `# 第N章`

**根因**：OCR 对页面顶部小字章节号识别率不稳定

**修复**：用语义锚点（`# 学习目标` + `通过本章学习`）替代格式锚点。每章必有学习目标段落

**注意**：codex review 指出"学习目标"锚点不通用，**很多教材没有这个结构**。所以 `skeleton/split.py` 设计成 strategy chain，这只是 strategy 3 的 fallback，不是默认。

**Skeleton 已修复**：`skeleton/split.py` 的 `split_chapters()` 多策略 chain：toc-first → h1-size → semantic-anchor → llm 兜底

---

## P4 ⚡⚡ 章节路由 80% 选第 1 章 → skill 形同虚设

**现象**：所有题目的 routing 结果都是第 1 章

**根因**：第 1 章是总论，关键词最宽泛（"管理会计"、"成本"、"决策"），匹配所有题

**修复**：routing prompt 改为通用规则"过宽章节降权"（不写死章号），并改为 top-k 选 1-2 章节

**Skeleton 已修复**：`prompts/routing.md` 含通用规则；`bench.py` 的 `route_chapter_topk()` 支持 top-k

---

## P5 ⚡⚡ MCQ 评分提取太严格 → 大量 "无法提取选项"

**现象**：WITH skill 答错率高，但仔细看 raw_answer LLM 答得是对的

**根因**：LLM 加了 "答案是 B" / 用 markdown 加粗 / 先分析后给答案，简单的 `if first_char in ABCD` 取不到

**修复**：5 层 fallback 提取器：
1. 单字符
2. 尾部 200 字找 "答案是 X" / "选 X" 等模式
3. `**X**` / `"X"` / `[X]` 包裹
4. 全文最后一个出现的 ABCD 字母

**Skeleton 已修复**：`skeleton/bench.py` 的 `extract_mcq_letter()`

---

## P6 ⚡⚡ OCR 上传慢成瓶颈 → 流水线被卡 1 小时

**现象**：MinerU OSS 上传 ~14KB/s，76MB 大书要 1.5 小时

**根因**：上海 OSS 国内访问网络瓶颈

**修复**：
- 切块上传（200 页/块）+ 并行多块（实测并发更快）
- 缓存 OCR 结果到磁盘，重跑 pipeline 时用 `--ocr-cache` 跳过
- 给用户 ETA + 后台跑

**Skeleton 已修复**：`skeleton/ocr_mineru.py` 的 `split_pdf_for_mineru()` 自动按 200 页切块；`pipeline.py` 支持 `--ocr-cache`

---

## P7 ⚡⚡ 抽取 prompt 不强 → LLM 输出软绵无力

**现象**：抽取后的章节文件结构正确但内容平庸（"本章主要介绍了..."）

**根因**：prompt 只给了模板没给反例 / 没强调密度

**修复**：prompt 必须包含：
- 明确"写给机器看不是给学生看"
- 反例（❌ 不要这样写）
- "数字、公式、术语 100% 准确"
- "第一行直接是 #，不要任何前言"

**Skeleton 已修复**：`prompts/extraction.md` 含完整反例 + 硬性要求

---

## P8 ⚡ 抽取后 LLM 把术语简化 → 关键词不准

**现象**：教材原文是 "企业使命"，LLM 抽取成 "使命"；description 关键词不精准

**根因**：LLM 默认会"凝练"

**修复**：prompt 加 "术语保留教材原貌（不要翻译、同义改写、口语化）"

**Skeleton 已修复**：`prompts/extraction.md` 硬性要求 #2

---

## P9 ⚡ system prompt 让 LLM "基于参考回答" → LLM 复述参考变得过于精简

**现象**：WITH skill 答得反而比 WITHOUT 短

**根因**：LLM 看到精简的章节参考就给精简答案

**修复**：system prompt 强制：
- "主动展开"
- "公式保留符号 + 含具体数字示例"
- "若问区别/对比，把所有维度全部列出"
- "若参考章节不覆盖问题，明确说'本章未覆盖'后基于通用知识回答"

**Skeleton 已修复**：`bench.py` 的 `answer_with_skill()` 内嵌 system prompt 含这些指令

---

## 通用经验

### 数据流验证检查点

每一步交付物都要打印验证信息，让人/Claude 自己看：

```
[probe]   pages=N, has_text_layer=true/false, language=ch
[ocr]     markdown 长度=X 字符
[split]   strategy=toc-first 识别 N 章
[extract] 章节 1/N: 输入 X 字 → 输出 Y 字
[assemble] SKILL.md 字符数, description 字符数 (上限 1536)
[bench]   30 题 WITH x% / WITHOUT y% / +Δ% (McNemar p=z)
```

### 失败时的反应模式

- **数据问题**（OCR 错乱、章节数不对）→ STOP 给用户看，让用户决定继续/重做
- **API 问题**（key 失效、超 quota）→ 立刻报错，告诉用户怎么续
- **LLM 输出格式错**（JSON 解析失败、缺字段）→ 重试 1 次，仍失败 STOP
- **benchmark 显示差距 < 5%** → **STOP 不要硬交付**，问用户下一步

---

## V0 实测背景

这些坑都是在一本 330 页中文管理会计教材上跑 V0 时实测发现的。V0 包含三个独立脚本：
- 主 pipeline (OCR + 切章 + 抽取 + 组装)
- benchmark 出题
- WITH/WITHOUT 评分

关键迭代轨迹：
- 章节切分 v1→v2→v3 的演进
- 抽取 prompt v1→v2 的强化
- benchmark 修 max_tokens / 修 routing 后从 +0% 到 +6.5% 总差距

所有迭代经验已固化进 `skeleton/` 模块和当前 `prompts/` 模板，不需要重复踩坑。
