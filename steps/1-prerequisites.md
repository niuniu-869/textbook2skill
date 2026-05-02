# Step 1: 准备

收集 3 个决策。**严格按 D-编号 / ELI10 / Stakes / Recommendation / Pros-Cons / Net 格式**用 AskUserQuestion 问。这一步无 skeleton 代码（纯交互）。

## D1: PDF 路径

如果用户调用时已给 PDF 路径，跳过 D1。否则用 AskUserQuestion 问绝对路径。

收到后用 `pdfinfo "<path>"` 验证文件存在 + 是 PDF。失败时 STOP 让用户重给。

## D2: skill 名

从书名建议 pinyin slug。比如《高级管理会计理论与实务》→ `gao-ji-guan-li-kuai-ji`。

```
D2 — skill 名

ELI10: 这个名字会变成 /skill-name slash 命令，也是 ~/.claude/skills/<这个名字>/ 的目录名。lowercase + hyphen 格式。

Stakes if we pick wrong: 后续可以 mv，但 description 路径会变；用户已经习惯的 /command 也会失效。

Recommendation: gao-ji-guan-li-kuai-ji 因为基于书名 pinyin，读起来明确

Note: options differ in kind, not coverage — no completeness score

Pros / cons:

A) gao-ji-guan-li-kuai-ji  (recommended)
  ✅ 直接来自书名，路由命中率高
  ✅ 跟 Claude Code 现有 skill 命名风格一致
  ❌ 拼音长，敲命令稍微累

B) 自定义（用户输入）
  ✅ 用户可以选短的（如 "gck"）或语义的（如 "mgmt-acct"）
  ❌ 偏离书名后路由准确率会下降

Net: 默认推荐拼音 slug，命名简短或英文化是可选的取舍
```

## D3: 安装位置

```
D3 — 装到哪？

ELI10: 个人位置（~/.claude/skills/）所有项目都能用；项目位置（.claude/skills/）只在当前 git repo 用，但能 commit 让团队共享。

Stakes: 选错可以 mv，但 description 里的"使用建议"路径会失效，要重写。

Recommendation: 个人 — 这个 skill 是教材知识，跨项目都有用，没有项目特异性

Pros / cons:

A) 个人 ~/.claude/skills/<name>/  (recommended)
  ✅ 跨所有项目可用，一次装到处用
  ✅ 不污染当前 git repo
  ❌ 不能 commit 共享给团队（每人自己装）

B) 项目 .claude/skills/<name>/
  ✅ 可 commit 进 git，团队共享
  ✅ 不会跟其他项目的同名 skill 冲突
  ❌ 切到别的 repo 就用不了

Net: 教材通用就个人，项目专属就项目
```

## 输出确认表

收齐 D1-D3 后输出确认表：

```
计划:
  PDF: /path/to/book.pdf
  skill 名: gao-ji-guan-li-kuai-ji
  安装位置: ~/.claude/skills/gao-ji-guan-li-kuai-ji/
  benchmark: 必跑（不可跳过）

下一步: step 2 探测 PDF
```

## 不要在这步问的事

- OCR 提供商 → 留到 step 3，因为 PDF 可能有文字层根本不需要 OCR
- LLM 选择 → 留到 step 5
- 单本切块策略 → step 3 自动按 200 页切
- 是否跑 benchmark → 不可跳，不问

> **原则**：每个决策延后到必须做时再问，避免一次问 10 个让用户疲劳。
