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

## 实测案例：《高级管理会计理论与实务》

V0 跑通的第一本书，整个过程的真实数据。

**输入**
- 330 页扫描版 PDF / 76MB / 中文 / 11 章
- 处理时长：~10 分钟（不含 MinerU OCR 网络等待 ~15 分钟）

**Benchmark（30 道原创题，覆盖所有 11 章）**

| 维度 | WITH skill | WITHOUT skill | Δ |
|------|-----------|---------------|---|
| 总分 | 90.3% (28/31) | 83.9% (26/31) | **+6.5%**（McNemar 不显著） |
| Easy | 90% | 90% | +0% |
| Medium | 87% | 87% | +0% |
| **Hard** | **83%** | 67% | **+17%** |
| **第 2 章（公式密集）** | **4/4 (100%)** | 2/4 (50%) | **+50%** |
| 其余 10 章 | 89% | 89% | +0% |

**章节路由准确率**：~90%

**关键观察**

1. **DeepSeek-v4-flash 对管理会计基础题 baseline 已经 84%** — 总差距 +6.5% 在统计噪声内
2. **真正加分集中在两个场景**：
   - 第 2 章（标准成本系统：19 个公式 + 完全成本法 vs 变动成本法）→ +50%
   - Hard 难题（多步推理 / 教材独有口径） → +17%
3. **简单概念题 LLM 自带知识就够** → Easy 0%

**结论**

主流学科（管理会计、会计学这类 LLM 训练充分的领域）：skill 在公式密集章节 + 难题上有显著价值，主流概念上提升有限。

**对比假设**：LLM 不熟悉的冷门领域（特定行业法规 / 公司内部 SDK / 小众专业）应该看到 +30%+ 的差距。这是 textbook2skill 的真正杀手场景。

完整 V0 跑通的 skill 已装在 `~/.claude/skills/gao-ji-guan-li-kuai-ji/`（参考形态）；详细数据在 `pitfalls.md` 里。

## 限制

- 中文教材测试充分，英文教材没系统测过（OCR + LLM prompt 应该兼容）
- 主流学科 baseline LLM 强，skill 增益小（见上方实测案例）
- **真正的杀手场景是 LLM 不熟悉的领域**——欢迎 PR 在冷门领域跑出 +30% 的 case
- Benchmark 30 题是 smoke test 不是 production-grade evaluation

## 路线图（未来 Claude 可按需扩展）

- [ ] 多 OCR 提供商（Mistral OCR / Anthropic Files / 自部署 marker）
- [ ] 多 LLM 提供商（统一 OpenAI-compatible 接口已留扩展点）
- [ ] LLM-as-judge 评分兜底（prompts/question-grader.md 已留模板）
- [ ] 增量更新（新版本教材增量重抽取）
- [ ] Web UI（可选，单 PDF drag-drop）
- [ ] 跨教材组合（让 Claude 同时用多个 skill 协同回答）
