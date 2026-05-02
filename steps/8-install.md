# Step 8: 安装

把组装好的 skill 目录复制到目标位置。**这一步无 skeleton 代码** — 是交互式的（确认 + 备份 + 复制）。

## D6: 覆盖确认（用 AskUserQuestion 问）

如果目标位置已经有同名 skill，**STOP 问用户**：

```
D6 — 已有同名 skill，怎么办？

ELI10: 目标位置 ~/.claude/skills/<name>/ 已存在（修改时间: <date>）。覆盖会丢失旧版本。

Stakes if we pick wrong: 直接覆盖丢失旧版本无法恢复。

Recommendation: 备份后覆盖 — 最安全，旧版本可恢复

Pros / cons:

A) 备份后覆盖 (recommended)
  ✅ 旧版本 mv 到 <name>.bak.<timestamp>，可恢复
  ✅ 立刻能用新版本
  ❌ 备份会占额外磁盘空间（按 KB 级，可忽略）

B) 直接覆盖
  ✅ 干净，不留备份
  ❌ 旧版本永久丢失，无法回退

C) 取消，用别的名字
  ✅ 保留旧版本
  ❌ 需要重起 step 1，重新决定 skill_name
```

## 安装命令（按 D6 选择）

### A) 备份后覆盖（默认）

```bash
DEST="$HOME/.claude/skills/<name>"
TS=$(date +%s)
[ -d "$DEST" ] && mv "$DEST" "${DEST}.bak.${TS}"
mkdir -p "$HOME/.claude/skills"
cp -r <build_dir>/skill "$DEST"
```

### B) 直接覆盖

```bash
DEST="$HOME/.claude/skills/<name>"
rm -rf "$DEST"   # 用户已明确确认，可以 rm
cp -r <build_dir>/skill "$DEST"
```

### 项目位置

把 `$HOME/.claude` 换成 `.claude`，目录改为 `.claude/skills/<name>/`：

```bash
mkdir -p .claude/skills
cp -r <build_dir>/skill .claude/skills/<name>
# 注意：.claude/skills 一般会 commit 进 git
```

## 安装后验证

```bash
ls -la "$DEST/"
# 应该看到 SKILL.md + chapters/ 目录

head -10 "$DEST/SKILL.md"
# 应该看到 frontmatter (--- name / description / when_to_use)
```

## 给 Claude Code 通知 skill 注册

Claude Code 自动 watch `~/.claude/skills/` 目录变更，**新装的 skill 在当前 session 立刻可用**。

但**当前 session 已经把 skill 列表加载进 context**，所以这个 session 内 LLM 自动路由可能不命中新 skill（除非 context 被刷新）。

让用户：
- 在当前 session 试用：直接 `/<skill-name>` 显式调用
- 或者新开一个 session：自动路由会命中

## DONE 报告

```
DONE — skill `<name>` installed at <path>

Coverage: <N> 章, <X> 个核心概念
Benchmark: WITH <x>% / WITHOUT <y>% / Δ +<z>% (McNemar p=<p>)
路由准确率: <r>%
判断: <强烈推荐 / 推荐 / 价值有限 / 不建议交付>

试用方式:
  方式 1（当前 session）: /<name> 后接你的问题
  方式 2（新 session）: 直接问相关问题，Claude 自动路由

文件位置: <path>
处理日志: <build_dir>/

下一步建议:
- 试问 5 个相关问题验证 skill 工作
- 如果效果不理想，回到 step 5 调 prompt 重做（用 --ocr-cache 跳过 OCR）
- 如果效果好，可以把 chapters/ 提交到 git 让团队共享
```

## 失败模式

| 现象 | 原因 | 修复 |
|------|------|------|
| `cp: permission denied` | 没权限写 ~/.claude/skills | 检查目录权限，或换 sudo |
| Claude Code 不识别新 skill | watch 没触发 | 重启 Claude Code session |
| `/<name>` 命令无效 | name 含非法字符 | 重新组装，确保 name 是 lowercase + hyphen + 数字 |
| 装后 skill 自动触发但回答怪 | description 关键词太宽 | 编辑 SKILL.md frontmatter 缩窄关键词 |
| benchmark 报"价值有限"但用户坚持装 | 已警告，最终用户决策 | 装上后让用户实际用试，不行可 `/uninstall <name>` |

## "不建议交付"时的引导

如果 step 7 报"不建议交付"，**STOP 默认不装**。AskUserQuestion 问：

```
benchmark 显示 skill 反而拖累 LLM。建议:
A) 不装，回 step 5 调 extraction prompt 后重跑
B) 还是装上（用户自担风险）
C) 取消整个流程
```
