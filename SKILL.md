---
name: textbook2skill
description: 把 PDF 教材编译成 Claude Code skill。引导用户走 OCR → 章节切分 → LLM 抽取 → skill 组装 → benchmark 验证 → 安装。本 skill 提供最小可执行 Python 骨架（skeleton/）和详细步骤说明，未来 Claude 按步骤执行 + 在每个关键决策点用 AskUserQuestion 询问用户（OCR 提供商 / LLM 提供商 / API key / 安装位置 / 是否覆盖等）。处理 300 页教材约 10 分钟（不含 OCR 网络等待）。
when_to_use: 用户明确提供 PDF 教材路径并请求生成 Claude Code skill。触发关键词："把这本书做成 skill"、"compile textbook"、"PDF 转 skill"、"textbook2skill"。**不要**在没有 PDF 路径时主动建议；**不要**用于生成非教材类内容。
disable-model-invocation: true
allowed-tools: Bash(python3 *) Bash(curl *) Bash(qpdf *) Bash(pdfinfo *) Bash(pdftotext *) Bash(cp *) Bash(mv *) Bash(mkdir *) Bash(ls *) Bash(cat *) Bash(file *) Bash(rm *) Read Write Edit Glob Grep
---

# textbook2skill

把任何 PDF 教材编译成 Claude Code skill。

**这个 skill 提供最小可执行骨架（`skeleton/*.py`）+ 步骤说明（`steps/*.md`）+ V0 实测踩过的坑（`pitfalls.md`）。** 未来 Claude 按步骤执行，遇到 OCR / LLM 调用就用骨架代码，遇到关键决策就 AskUserQuestion 问用户。

## 核心原则（必读）

1. **没有 benchmark 就没有 skill** — 任何 skill 在交付前必须跑 WITH/WITHOUT 对比。30 题 smoke test 是底线，不是判决；差距 < 5% 时**STOP 不要硬交付**
2. **教材是为 AI 阅读做了 100 年预演的语料** — 章节=chunking、例题=few-shot、习题=eval
3. **输出 skill 是给机器看的不是给学生看的** — 密度优先，不要"学习指南"语气
4. **绝不传 max_tokens 和 temperature** — DeepSeek-v4-flash 等 reasoning 模型设了 max_tokens 反而 content 为空（V0 实测踩过的硬坑）
5. **关键决策必须问用户** — OCR 厂商 / LLM 厂商 / API key / 覆盖确认 — 用 AskUserQuestion 严格按 D-编号 / ELI10 / Stakes / Recommendation / Pros-Cons / Net 格式问

## 工作流总览

```
[1] prerequisites  问 PDF 路径 + skill 名 + 安装位置
[2] probe          探测 PDF (有无文字层 / 页数 / 语言)
[3] ocr            问 OCR 厂商（默认 MinerU）→ 引导用户给 key → 跑 OCR
[4] split          多策略章节切分 (TOC-first → H1+size → 语义锚点 → LLM 兜底)
[5] extract        问 LLM 厂商（默认 DeepSeek 因为便宜）→ 引导给 key → 并发抽取
[6] assemble       组装符合 Claude Code skill spec 的目录
[7] bench          【必跑】30 题 smoke test → WITH vs WITHOUT → 给"是否可交付"判断
[8] install        默认 backup-then-copy（不 rm -rf）→ user 确认覆盖
```

每步详见 `steps/<N>-*.md`，对应骨架代码在 `skeleton/<module>.py`。**按需 Read 加载，不要一次性读全部**。

## 步骤路由表

| 步骤 | 详细步骤说明 | 骨架代码 | 输入 → 输出 |
|------|-------------|---------|-------------|
| 1. 准备 | [steps/1-prerequisites.md](steps/1-prerequisites.md) | — | (用户输入) → `config.json` |
| 2. 探测 | [steps/2-probe.md](steps/2-probe.md) | [skeleton/probe.py](skeleton/probe.py) | `pdf` → `probe.json` |
| 3. OCR | [steps/3-ocr.md](steps/3-ocr.md) | [skeleton/ocr_mineru.py](skeleton/ocr_mineru.py) | `pdf` → `book.md` |
| 4. 切章 | [steps/4-split.md](steps/4-split.md) | [skeleton/split.py](skeleton/split.py) | `book.md` → `chapters.json` |
| 5. 抽取 | [steps/5-extract.md](steps/5-extract.md) | [skeleton/extract.py](skeleton/extract.py) | `chapters.json` → `extracted/*.md` |
| 6. 组装 | [steps/6-assemble.md](steps/6-assemble.md) | [skeleton/assemble.py](skeleton/assemble.py) | `extracted/*.md` → `skill/` |
| 7. bench | [steps/7-bench.md](steps/7-bench.md) | [skeleton/bench.py](skeleton/bench.py) | `skill/` → `benchmark.json` + 报告 |
| 8. 安装 | [steps/8-install.md](steps/8-install.md) | — | `skill/` → `~/.claude/skills/<name>/` |

**编排器**: [skeleton/pipeline.py](skeleton/pipeline.py) 串起 step 2-7（不含交互式步骤 1 和 8）

## 关键 prompt 模板

| 用途 | 文件 |
|------|------|
| 章节抽取 | [prompts/extraction.md](prompts/extraction.md) |
| 章节路由（top-k） | [prompts/routing.md](prompts/routing.md) |
| benchmark 出题 | [prompts/question-gen.md](prompts/question-gen.md) |
| benchmark 评分 | [prompts/question-grader.md](prompts/question-grader.md) |

## 失败模式 & 恢复

每个失败给用户**具体的下一步**，不要"看 log"：

- **PDF 上传慢** → 网络瓶颈，提示 ETA + 后台跑 + 缓存避免重传
- **章节数明显不对** → 切到下一个 split strategy（TOC → H1 → 锚点 → LLM 兜底），全部失败时让用户手动指认章节起点
- **路由总选第 1 章** → routing prompt 启用"过宽章节降权"（不写死章号，按关键词宽泛度判断）
- **WITH 答得太精简** → extraction prompt 强制"主动展开 + 公式保留符号"
- **LLM 返回空 content** → 检查是否误传了 max_tokens（reasoning 模型陷阱）
- **benchmark 显示差距 < 5%** → **明确告诉用户：这个领域 LLM baseline 已经强，skill 价值有限**，不要硬交付

完整清单见 [pitfalls.md](pitfalls.md)（V0 实测 9 大坑）。

## 决策点（统一 AskUserQuestion 格式）

每个决策严格按 D-编号 / ELI10 / Stakes / Recommendation / Pros-Cons / Net 格式问。最多 ~6 个询问点，不要一次问 10 个。

| 编号 | 时机 | 问什么 |
|------|------|--------|
| D1 | step 1 | PDF 路径（如未提供） |
| D2 | step 1 | skill 名（自动建议 pinyin slug） |
| D3 | step 1 | 安装位置（个人 vs 项目） |
| D4 | step 3 | OCR 厂商（首推 MinerU），并提示给 key |
| D5 | step 5 | LLM 厂商（首推 DeepSeek-v4-flash 便宜），并提示给 key |
| D6 | step 8 | 安装确认（覆盖现有 skill 时） |

`step 7` benchmark 必跑不询问。

## DONE 报告模板

成功完成时按这个格式输出：

```
DONE — skill `<name>` installed at <path>
Coverage: N 章, X 个核心概念
Benchmark: WITH x% / WITHOUT y% / Δ +z% (95% CI: [a, b])
路由准确率: A%
判断: <强烈推荐 / 推荐 / 价值有限 / 不建议交付>

Try it now:
  ask "<示例问题>" — Claude 应自动路由到这个 skill

Skill files: <path>
Logs: /tmp/textbook2skill-XXX/
```

## 反例（不要这样做）

- ❌ 跳过 benchmark 直接交付（"看着差不多就行"）
- ❌ 让 Claude 自己决定 skill 名 / 安装位置（应该问用户）
- ❌ 抽取 prompt 写成"请把这章总结一下"（输出会软绵无力）
- ❌ 章节切分只用一个策略（OCR 错乱必坏，要 strategy chain）
- ❌ 给 LLM 设 max_tokens（reasoning 模型可能空 content）
- ❌ 全部章节串行处理（DeepSeek 支持高并发，并行差 10x）
- ❌ benchmark 用教材原题（必须**原创题**测同样考点）
- ❌ benchmark 把 +6% 包装成"差距"（区间内可能是噪声，要算置信区间）
- ❌ 安装时 `rm -rf` 旧 skill（默认 backup-then-copy）

## 给未来 Claude 的指引

1. **不要重新发明轮子** — 按 steps/ 顺序执行，遇到 OCR/LLM 调用直接用 `skeleton/*.py`
2. **遇到坑去查 [pitfalls.md](pitfalls.md)** — 9 大坑都是 V0 实测踩过的
3. **不要省略 benchmark** — 这是判断"是否可交付"的唯一硬证据
4. **失败时 STOP 问用户**，不要硅 fallback — 恢复决策应该用户做
5. **Skeleton 是起点不是终点** — 你可以按需修改/扩展（增加 OCR 厂商、换 LLM、加错误处理），但保持模块边界
