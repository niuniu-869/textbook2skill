# Step 5: LLM 抽取章节

把每章 markdown 用 LLM 压缩成**密度极高、可被 Claude 直接消费**的 skill 片段。

## D5: LLM 提供商（用 AskUserQuestion 问）

```
D5 — 选 LLM 抽取提供商

ELI10: 用 LLM 把每章原文压缩成结构化 skill 片段。中文质量、长 context、价格是关键。

Stakes if we pick wrong: 选差 LLM → 抽取质量低（公式丢、术语简化）→ skill 没价值。

Recommendation: DeepSeek-v4-flash — 中文好 + 32K context + 极便宜（单本书成本 < ¥1）

Pros / cons:

A) DeepSeek-v4-flash (recommended)
  ✅ 中文优秀，公式/术语保留好
  ✅ 价格极低，11 章并发 30 秒搞定
  ❌ 是 reasoning 模型，**绝不能传 max_tokens 否则 content 为空**

B) Claude Sonnet 4.x
  ✅ 200K context，能装超长章节
  ✅ 中文质量顶级
  ❌ 单本成本 ~10 倍 DeepSeek

C) GPT-4o / GPT-5
  ✅ 已有 OpenAI 账号的话现成
  ❌ 中文略弱于 DeepSeek，价格高

D) 用户已有其他 OpenAI-compatible API
  ✅ 灵活，可用任何兼容服务
  ❌ 需要用户给 base_url + key，没默认配置

Net: 默认 DeepSeek，预算多就 Claude Sonnet
```

## 引导用户给 key

如果对应 env 已设跳过；否则 AskUserQuestion 问：

```
请提供 DeepSeek API key。获取方式：
1. 访问 https://platform.deepseek.com
2. 注册 → API Keys → 创建 → 复制
3. 设到环境变量:
   export DEEPSEEK_KEY=<your-key>
```

## 跑抽取

调骨架:

```bash
python3 ${SKILL_DIR}/skeleton/extract.py \
  <chapters.json> \
  <output_dir> \
  ${SKILL_DIR}/prompts \
  [provider]   # 默认 deepseek
```

## I/O 契约

输入: `chapters.json`（来自 step 4）+ `prompts/extraction.md` + LLM env key

输出: `<output_dir>/01-第1章_xxx.md`、`<output_dir>/02-第2章_xxx.md` ... 每章一个

## ⚠️ 关键约束

### 绝不传 max_tokens / temperature

DeepSeek-v4-flash 是 reasoning 模型 — 内部 reasoning_tokens 占用预算，max_tokens 太小时 content 字段返回空字符串。

`skeleton/llm.py` 的 `chat()` 方法已经强制不传，遇到空 content 会抛异常。

### 用并发，不要串行

`extract.py` 的 `extract_all()` 默认 `max_workers=11`。DeepSeek 支持高并发，串行会慢 10x。

## 抽取 prompt（核心资产）

详见 [prompts/extraction.md](../prompts/extraction.md)。要点：

1. **明确"写给 Claude 看不是给学生看"** — 不要"学习指南"语气
2. **强制结构**：核心概念 / 公式与计算口径 / 方法/流程 / 例题 / 易混点 / 关联
3. **含反例** — 明确告诉 LLM 不要输出 "本章主要介绍..." 这种废话
4. **保留教材原貌** — 术语不翻译、不改写、不简化（"企业使命" 不要简化为 "使命"）
5. **OCR 错乱标 [OCR错乱]** — 不让 LLM 自圆其说
6. **数字精确度** — 例题里所有数字必须保留，不能写"按公式计算"代替具体数字

## 验证单章抽取质量

抽取完一章后**必须看一眼**：
- `## 核心概念` 至少 4 个 bullet，有 `**术语**: 定义` 格式
- `## 公式与计算口径` 公式数 ≥ 章节实际公式数 70%
- `## 例题` 含具体数字（不是"某产品某成本"）
- 总长度：章节字符 / 输出字符 = 5x ~ 10x（压缩比合理）

如果输出过短（压缩比 > 15x） → prompt 加强 "主动展开"
如果输出过长（压缩比 < 3x） → prompt 加强 "密度优先"

## 失败模式

| 现象 | 原因 | 修复 |
|------|------|------|
| `LLM returned empty content` | 设了 max_tokens | 检查 llm.py，确认没传 |
| 输出 "我来帮你抽取..." 开场白 | prompt 没禁止 | 在 prompt 加 "第一行直接是 #" |
| 数字被抹掉 | 过度压缩 | prompt 强调"例题必须含具体数字" |
| 术语被简化 | LLM 默认行为 | prompt 加 "术语保留教材原貌" |
| 个别章节失败 | 单点 LLM 错误 | extract.py 已捕获，写占位文件 `[抽取失败]`，benchmark 时这章会路由不到 |
