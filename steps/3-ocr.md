# Step 3: OCR

把 PDF 转成 markdown。这一步的目标是拿到一份**含章节标题、段落、公式、表格**的 markdown 文件，作为后续切章 + 抽取的输入。

## 决策树（先看 step 2 的 probe 结果）

- **`needs_ocr: false`**（PDF 有文字层）→ 直接 `pdftotext "<PDF>" book.md`，**跳过 OCR**
- **`needs_ocr: true`** → 进入下方 OCR 提供商选择

## D4: OCR 提供商（用 AskUserQuestion 问）

```
D4 — 选 OCR 提供商

ELI10: 把扫描版 PDF 转成可读 markdown。中文教材公式表格识别质量差异大。

Stakes if we pick wrong: 选低质提供商 → markdown 乱码或公式丢 → 下游 LLM 抽取直接幻觉。

Recommendation: MinerU — 中文教材公式表格识别最好，免费额度大

Pros / cons:

A) MinerU (recommended)
  ✅ 中文识别最强 + 免费额度足够测试
  ✅ VLM 模式支持公式 LaTeX + 表格 markdown
  ❌ 上海 OSS 上传慢（实测 ~14KB/s），大书需要 1+ 小时

B) Mistral OCR
  ✅ 上传速度快
  ❌ 中文公式识别较弱，收费

C) 自部署 marker-pdf
  ✅ 本地跑，零网络成本
  ❌ 需要 GPU，安装复杂

D) 用户自己已经有 OCR 好的 markdown
  ✅ 跳过最慢的一步
  ❌ 需要用户文件存在并已可用

Net: MinerU 是最稳的默认；如果用户已有 markdown，D 是最快路径
```

## 选 MinerU 后引导用户给 token

如果 `MINERU_TOKEN` 环境变量已设，跳过；否则 AskUserQuestion 问：

```
请提供 MinerU API token。获取方式：
1. 访问 https://mineru.net
2. 注册 → 控制台 → API Token
3. 复制 token，设到环境变量:
   export MINERU_TOKEN=<your-token>
4. 然后告诉我"已设置"

或者直接粘贴 token，我就在这次 session 用（不持久化）
```

## 跑 OCR

调骨架:

```bash
# 自动处理大书切块
python3 ${SKILL_DIR}/skeleton/ocr_mineru.py "<PDF>" "<output_dir>"
```

输出: `<output_dir>/<batch_id>/full.md`（多块时合并到 `<output_dir>/full-merged.md`）

## I/O 契约

| | 输入 | 输出 |
|---|---|---|
| 单文件 OCR | `book.pdf` | `<batch_id>/full.md` |
| 多块 OCR | `book.pdf` (>200 页) | 多个 `<batch_id>/full.md` + 合并的 `full-merged.md` |
| OCR 缓存 | `MINERU_TOKEN` env | 写到 `<batch_id>/` 整套结果（含 zip / json / images） |

## 验证 OCR 质量

OCR 完成后**必须人眼扫一眼**：

```bash
head -200 <output>/full.md
# 检查：是不是中文（不是乱码）、章节标题是不是 # 开头、公式有没有 $...$ 包裹
```

如果质量差：
- 中文乱码 → `language` 字段没设 "ch"（编辑 ocr_mineru.py 改）
- 公式丢失 → 没开 `enable_formula: true`
- 表格变图片 → 没开 `enable_table: true`
- 章节标题没识别 → MinerU layout 失败，换提供商

## OCR 错乱处理

OCR 100% 准确不存在。常见错误：
- 数字混淆：1/l/I, 0/O/o
- 中英文标点混淆：。/. ，/,
- 上下角标丢失：x² → x2
- 公式符号错：∑ → Σ

**核心原则：不让下游 LLM 自圆其说**。抽取 prompt（step 5）已经告诉 LLM：
> 如果原文 OCR 错误明显（乱码、缺字），用 `[OCR错乱]` 标注，**不要尝试还原**

## 失败模式

| 现象 | 原因 | 修复 |
|------|------|------|
| 上传 1h 不完成 | 网络瓶颈 | 后台跑 + 写 OCR 缓存 + 给用户 ETA |
| OCR 任务一直 `waiting-file` | OSS 上传没完成或失败 | 重传 |
| 下载的 zip 没有 full.md | MinerU 解析失败 | 换 model_version 或换提供商 |
| markdown 乱码 | language 设错了 | 重提交，确认 language=ch |
| `MINERU_TOKEN 未设置` | env 没 export | 让用户重新提供 |

## 跳过 OCR 的快速通道

如果用户已有 markdown（之前跑过 OCR、自己手动 OCR 过），用 `--ocr-cache` 跳过：

```bash
python3 ${SKILL_DIR}/skeleton/pipeline.py \
  --ocr-cache /path/to/existing/book.md \
  ...
```

省下 1 小时网络等待。
