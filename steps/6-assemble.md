# Step 6: skill 组装

把抽取出的章节文件组装成符合 Claude Code skill spec 的目录。

## 命令

```bash
python3 ${SKILL_DIR}/skeleton/assemble.py \
  <extracted_dir> \
  <output_dir> \
  <skill_name> \
  "<book_title>"
```

## 输出目录结构

```
<output_dir>/
├── SKILL.md                # 入口 + 路由表（< 500 行）
└── chapters/
    ├── 01-第1章_xxx.md
    ├── 02-第2章_xxx.md
    └── ...
```

## SKILL.md 模板（assemble.py 自动生成）

frontmatter 自动生成：
- `name`: 用户在 step 1 给的 slug
- `description`: 自动构造（章节主题 + 关键词，前 1500 字符）
- `when_to_use`: 关键词列表（前 1500 字符）

主体：
- 使用流程（5 步）
- 章节速查表（markdown 表格，每章一行：章节 / 关键词 / 文件名）
- 反例（do/don't）

## 关键词提取（codex review 修订后）

`extract_keywords()` 函数从抽取后的 markdown 提关键词，**源扩展**（V0 只取核心概念是不够的）：

| 来源 | 解析方式 |
|------|---------|
| `## 核心概念` 的 `**术语**: 定义` | regex |
| `## 公式与计算口径` 的 `**公式名**:` | regex |
| `## 例题` 的 `### 例 X.M: topic` | regex |

去重后取前 8 个。这些关键词同时进 SKILL.md 章节速查表 + description + when_to_use。

## description 字符上限

`description + when_to_use` 总长 ≤ 1500 字符（留 36 字符给 frontmatter 边界，<1536 上限）。

`build_description()` 自动控制：
- description: `《<书名>》专家技能 — 覆盖<前 6 章主题>。用户问及<前 8 个关键词>时优先使用。`
- when_to_use: `用户问及以下任一概念时：<前 15 个关键词>`
- 总长超 1500 → 截断 when_to_use

## 章节速查表（关键路由 hint）

```
| 章节 | 关键词 | 文件 |
|------|--------|------|
| 第1章 管理会计概述 | 企业使命、企业目标、企业战略、管理流程、管理会计 | `chapters/01-...md` |
| 第2章 成本计算系统 | 成本动因、标准成本、价格差异、数量差异、变动成本法 | `chapters/02-...md` |
| ...
```

**为什么用表格而不是 bullet 列表**：
- LLM 一眼看到 章节↔关键词 映射
- 选章节时不需要去读章节内容，只看速查表
- V0 实测：路由准确率 90%+

## 验证组装结果

```
[assemble] 11 章 → /tmp/build/skill
[assemble] SKILL.md 1655 字符
[assemble] description+when_to_use 209 字符 (上限 1536)
[assemble] 关键词样例: ['企业使命', '企业目标', ...]
```

人眼检查:
- ✓ description+when_to_use < 1536
- ✓ 章节速查表的关键词不空
- ✓ 章节文件名不含特殊字符（assemble.py 已 sanitize）
- ✓ 章节速查表的章节顺序对（按 idx 排）

## 失败模式

| 现象 | 原因 | 修复 |
|------|------|------|
| description+when_to_use > 1500 | 关键词太多 | 缩到每章前 3 个关键词 |
| 关键词全是 "(待补)" | 抽取章节没有 `## 核心概念` 区块 | 检查 extracted/ 文件，可能 LLM 抽取失败了 |
| 章节速查表里某行没文件 | 章节文件名 sanitize 后跟代码引用不一致 | 检查 chapters_dir 实际内容 |
| 某章关键词全英文 | 教材是英文 | 不是 bug，照常运行 |

## 不要在这步做的

- 不跑 benchmark — 留到 step 7
- 不安装到 ~/.claude/skills/ — 留到 step 8
- 不显示给用户 SKILL.md 全文 — 太长，用 `head` 或路径引用
