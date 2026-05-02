# Step 4: 章节切分

把 OCR 出的 markdown 切成 `[(章节标题, 章节内容), ...]` 列表。

## 多策略 chain（按可靠性排）

`skeleton/split.py` 的 `split_chapters()` 会自动按下面顺序尝试，第一个产出 ≥3 章的胜出：

1. **toc-first**: 找 `# 目录` 区域提取章节列表 → 在正文 grep 标题位置
2. **h1-size**: 所有 H1 按字符量分组，长的（≥ 3000 字符）就是章节
3. **semantic-anchor**: 找"# 学习目标 + 通过本章学习"等固定开头（V0 教材的策略，不通用）
4. **llm fallback**: 让 LLM 看 markdown 头 + TOC 提议章节起点（需要 llm_client）

**Codex 反馈**：单一锚点过拟合 V0，必须 strategy chain。⚠️ "学习目标"锚点对没有这种结构的教材会失败，所以放在 strategy 3 而不是 1。

## 命令

```bash
python3 ${SKILL_DIR}/skeleton/split.py "<book.md>" "<chapters.json>"
```

## I/O 契约

输入: 一个 markdown 文件（OCR 输出 / 合并后的多块 markdown）

输出: `chapters.json`
```json
[
  {
    "idx": 1,
    "title": "第1章 管理会计概述",
    "content": "# 第1章\n\n# 管理会计概述\n\n# 学习目标\n\n通过本章学习...",
    "source_strategy": "toc-first",
    "num": "1"
  },
  ...
]
```

## TOC 提取

`extract_toc()` 函数从 markdown 开头的 `# 目录` / `# Contents` / `# Table of Contents` 区域提取章节列表。

返回 `["第1章 管理会计概述", "第2章 成本计算系统", ...]` 用于：
- 切分时规范化章节号
- 验证切分结果（识别章数应等于 TOC 章数）
- 生成 SKILL.md description（章节主题摘要）

## 验证切分结果

切完后**必须打印章节数 + 每章字数**：

```
[split] strategy=toc-first 识别 11 章
  [1] 第1章 管理会计概述 (17074 字符)
  [2] 第2章 成本计算系统 (58075 字符)
  ...
```

如果章节数和 TOC 不一致：
- 多了 → 锚点匹配多次（同一章被多个锚点触发），`split_chapters()` 已做去重，再多就排查
- 少了 → 某章 OCR 丢了所有锚点，降到下一个 strategy

如果章节数 < 3 → STOP 让用户检查 OCR 输出，或手动指认章节起点。

## 章节大小检查

每章字符数应该在 5K-60K 字符之间：
- < 5K → OCR 失败或章节切错（提前结束）
- > 60K → 单章过长，DeepSeek 32K context 装不下，需要按节再切（H2 级别）

`extract.py` 自动截断 > 30000 字符的章节并加 `[...章节后段省略...]` 标记。

## 失败模式

| 现象 | 原因 | 修复 |
|------|------|------|
| 识别章节数 = TOC 数 × 2 | TOC 条目和正文都被算 | `is_toc_line` 过滤逻辑应该已处理；调试看哪条没过滤 |
| 章节数比 TOC 少 1-2 | OCR 丢了某章节号 / 锚点 | 改 strategy（toc-first 失败 → h1-size） |
| 章节标题缺失 | 锚点找到但 H1 找不到 | 用 TOC 标题填补 |
| 单章 > 60K 字符 | 大章节没二级切分 | 按 H2 (`## N.M`) 再切，或截断 |
| 全部 strategy 失败 | 教材结构异常 | LLM 兜底（暂未实现）或让用户手动指认 |

## 扩展点

- 如果遇到不同结构的教材（如英文 textbook 用 `# Chapter N` 格式），加 strategy 函数到 `split.py` 的 `strategies` 列表
- LLM 兜底（strategy 4）的具体实现留给用户/Claude 按需补：让 LLM 看 markdown 前 5K + TOC，提议每章首行的 markdown 字符串，再 grep 在原文位置
