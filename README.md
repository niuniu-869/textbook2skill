# textbook2skill

把 PDF 教材编译成 Claude Code skill 的 meta-skill。

## 为什么是教材

**大学专业课课本就是地球上最适合做 AI skill 的语料。**

我们之前还误会过——以为有些课本"不讲人话"。其实人家早就在为 AI 阅读布局了：

- **章节结构** = 现成的 chunking（AI 不会一次性把全书塞进上下文）
- **例题** = 现成的 few-shot（每个概念都配了带数字的完整解题）
- **课后题** = 现成的 eval（自带验证 AI 是否真懂的考核）
- **公式与术语** = 已经 100% 精确化的领域语言（不需要再"提炼"）

没有比教材更适合炼化一个专业知识到 AI skill 的语料了。一本经典教材的作者花了几年甚至几十年把一个学科结构化、压缩、配套例题——我们要做的只是把这份成果搬到 LLM 能消费的形式里。

`textbook2skill` 就是这个搬运工。

## 是什么

一个 Claude Code skill，安装后通过 `/textbook2skill` 触发，引导用户走完整 pipeline：

```
PDF → probe → OCR → 切章 → LLM 抽取 → 组装 → benchmark → 安装
```

输出一个**经过 benchmark 验证**的、可装到 `~/.claude/skills/` 的领域知识 skill。

## 设计哲学

- **不替用户做决策**：OCR 厂商 / LLM 厂商 / 安装位置都问用户
- **Benchmark 必跑**：没有 benchmark 不交付（差距 < 5% 就 STOP）
- **最小骨架不锁定**：`skeleton/` 是参考实现，未来 Claude 可按需扩展
- **教材是为 AI 阅读做了 100 年预演的语料**：章节=chunking、例题=few-shot、习题=eval

## 安装

```bash
cp -r path/to/textbook2skill ~/.claude/skills/textbook2skill
```

或在项目下安装：

```bash
mkdir -p .claude/skills
cp -r path/to/textbook2skill .claude/skills/textbook2skill
```

## 使用

在 Claude Code 里直接 `/textbook2skill` 触发（disable-model-invocation 防止意外自动触发）。

或手动：
> 我有一本 PDF 教材在 /path/to/book.pdf，用 textbook2skill 帮我做成一个 skill

Claude 会按 `SKILL.md` 步骤跑，每个关键决策点用 AskUserQuestion 问用户。

## 目录结构

```
textbook2skill/
├── SKILL.md                          # ★ 入口，未来 Claude 第一个读这个
├── steps/                            # 8 个步骤的详细说明
│   ├── 1-prerequisites.md            # 收集 PDF 路径 / skill 名 / 安装位置
│   ├── 2-probe.md                    # 探测 PDF
│   ├── 3-ocr.md                      # OCR (默认 MinerU)
│   ├── 4-split.md                    # 章节切分（多策略）
│   ├── 5-extract.md                  # LLM 抽取 (默认 DeepSeek)
│   ├── 6-assemble.md                 # 组装 skill
│   ├── 7-bench.md                    # 必跑 benchmark
│   └── 8-install.md                  # 安装到 ~/.claude/skills/
├── prompts/                          # 4 个 prompt 模板
│   ├── extraction.md                 # 章节抽取
│   ├── routing.md                    # 章节路由 (top-k)
│   ├── question-gen.md               # benchmark 出题
│   └── question-grader.md            # benchmark 评分（可选）
├── skeleton/                         # 最小可执行 Python 骨架
│   ├── README.md                     # skeleton 用法
│   ├── llm.py                        # LLM 客户端抽象
│   ├── probe.py                      # PDF 探测
│   ├── ocr_mineru.py                 # MinerU OCR adapter
│   ├── split.py                      # 多策略章节切分
│   ├── extract.py                    # LLM 抽取
│   ├── assemble.py                   # skill 组装
│   ├── bench.py                      # benchmark + McNemar test
│   └── pipeline.py                   # 端到端编排器
├── pitfalls.md                       # V0 实测 9 大坑
└── README.md                         # 本文件
```

## 依赖

### 系统依赖
- `python3 >= 3.10`
- `requests` (`pip install requests`)
- `qpdf` (PDF 切块)
- `pdfinfo` + `pdftotext` (poppler-utils 包)

### API key（运行时按需提供）
- `MINERU_TOKEN` — 扫描版 PDF OCR 必需
- `DEEPSEEK_KEY` — LLM 抽取（默认）
- 或 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` — 用户选其他 LLM 时

## 给未来 Claude 的指引

1. **先读 [SKILL.md](SKILL.md)** — 入口 + 工作流概览
2. **按 steps/<N>-*.md 顺序执行** — 别跳步
3. **遇到 OCR/LLM 调用直接用 skeleton/**.py — 不重新发明轮子
4. **失败时 STOP 问用户** — 不要硅 fallback
5. **benchmark 必跑** — 这是判断"是否可交付"的唯一硬证据
6. **遇到坑查 [pitfalls.md](pitfalls.md)** — 9 大坑都是 V0 实测踩过的

## 设计依据

本 skill 的设计经过：
- V0 实跑（2026-05-02 在 330 页中文管理会计教材上）
- Anthropic 官方 Claude Code skill 规范对齐（https://code.claude.com/docs/en/skills）
- gstack 系列 skill 的交互模式参考（AskUserQuestion 严格格式）
- Codex 独立 review（指出 V0 的 7 个架构问题，全部修订）

## 限制

- 中文教材测试充分，英文教材没系统测过（OCR + LLM prompt 应该兼容）
- 主流学科 baseline LLM 强，skill 增益小（V0 实测 +6.5% 不显著）
- **真正的杀手场景是 LLM 不熟悉的领域**（特定行业法规 / 内部 SDK / 冷门专业）
- Benchmark 30 题是 smoke test 不是 production-grade evaluation

## 路线图（未来 Claude 可按需扩展）

- [ ] 多 OCR 提供商（Mistral OCR / Anthropic Files / 自部署 marker）
- [ ] 多 LLM 提供商（统一 OpenAI-compatible 接口已留扩展点）
- [ ] LLM-as-judge 评分兜底（prompts/question-grader.md 已留模板）
- [ ] 增量更新（新版本教材增量重抽取）
- [ ] Web UI（可选，单 PDF drag-drop）
- [ ] 跨教材组合（让 Claude 同时用多个 skill 协同回答）
