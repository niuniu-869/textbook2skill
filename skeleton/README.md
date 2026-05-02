# skeleton/ — 最小可执行骨架

这些 Python 文件提供 textbook2skill 的核心模块。**不是 production-ready，不要试图跑大书全自动化** — 要按 SKILL.md 的步骤走，让 Claude 在每个决策点跟用户互动。

## 模块依赖图

```
pipeline.py  (编排器：串 step 2-7)
├── probe.py             (step 2)
├── ocr_mineru.py        (step 3, MinerU 实现)
├── split.py             (step 4, 多策略章节切分)
├── extract.py           (step 5)
│   └── llm.py           (LLM 客户端抽象)
├── assemble.py          (step 6)
└── bench.py             (step 7, 必跑)
    └── llm.py
```

## 直接跑（仅供调试，建议按 step 走）

```bash
export MINERU_TOKEN=...
export DEEPSEEK_KEY=...

python3 pipeline.py \
  --pdf /path/to/book.pdf \
  --skill-name my-textbook \
  --book-title "教材名称" \
  --output /tmp/build \
  --prompts path/to/textbook2skill/prompts
```

## 模块单独使用

每个模块都可单独跑（`python3 module.py args`），方便迭代：

```bash
# 探测 PDF
python3 probe.py /path/to/book.pdf

# 只跑 OCR
python3 ocr_mineru.py /path/to/book.pdf /tmp/ocr-out

# 已有 markdown，只切章节
python3 split.py /tmp/book.md /tmp/chapters.json

# 已有章节，只跑抽取
python3 extract.py /tmp/chapters.json /tmp/extracted path/to/textbook2skill/prompts

# 已有抽取，只组装 skill
python3 assemble.py /tmp/extracted /tmp/skill my-name "教材名"

# 已有 skill，只跑 benchmark
python3 bench.py /tmp/skill /tmp/questions.json path/to/textbook2skill/prompts
```

## 设计原则

1. **每个模块单一职责** — 不做跨模块的"智能整合"
2. **stdout 友好** — 长任务 print 进度，不依赖 logging 框架
3. **失败就抛** — 不静默 swallow，让上层决策
4. **不传 max_tokens / temperature** — reasoning 模型陷阱（V0 实测）
5. **能并发就并发** — DeepSeek 支持高并发，串行是浪费

## 扩展点（注释里标了 TODO）

- **OCR 提供商**: 加 `ocr_<provider>.py`（参考 `ocr_mineru.py`）
- **LLM 提供商**: `llm.py` 的 `configs` 字典里加新条目
- **切章策略**: `split.py` 的 `strategies` 列表里加新 strategy 函数
- **评分指标**: `bench.py` 的 `build_report` 里加新维度

## 不在骨架里的（未来 Claude 按需补）

- **Web UI / drag-drop 上传** — 用户决定后再做
- **多用户 / 权限管理** — V0 单用户够用
- **OCR 进度 webhook / 自动重试 / 断点续传** — 需要时再加
- **完整 logging / metrics** — 可以接 sentry / posthog
- **CLI 子命令分组** — 可以包成 typer/click

## 设计依据

本骨架经过一次完整 V0 实跑（330 页中文管理会计教材）+ 独立 codex review 修订。详细踩坑记录在 [../pitfalls.md](../pitfalls.md)。
