# Step 2: 探测 PDF

把 PDF 元数据探出来，决定后续 OCR 路径。

## 命令

直接调骨架:

```bash
python3 ${SKILL_DIR}/skeleton/probe.py "<PDF>"
```

输出 JSON: `{path, pages, size_mb, has_text_layer, language, encrypted, needs_ocr}`

## 判断逻辑

| 字段 | 来源 | 用途 |
|------|------|------|
| `pages` | `pdfinfo` | 决定是否需要切块（MinerU > 200 页要切） |
| `has_text_layer` | `pdftotext -l 5` 字符数 > 1000 | 决定是否走 OCR |
| `language` | 探测中文字符 | 决定 MinerU 的 language 字段（ch / en） |
| `encrypted` | `pdfinfo` | 加密 PDF STOP |
| `needs_ocr` | `not has_text_layer and not encrypted` | 主决策 |

## STOP 触发条件

下面任一情况 STOP 用 AskUserQuestion 问用户：

- `encrypted: true` → "PDF 加密了，请提供解密版本或密码"
- `pages > 600` → "PDF 超过 600 页，处理成本会高，确认要全本处理吗？"
- `pages < 10` → "PDF 只有 N 页，不像教材，确认这是要做的输入吗？"
- `pdfinfo` 报错 → "PDF 文件读取失败，可能损坏"

## 给用户的探测报告

```
PDF 探测完成:
  路径: /path/to/book.pdf
  页数: 330
  大小: 76.9 MB
  文字层: 无 → 必须 OCR
  语言: 中文
  加密: 否

决策:
  ✓ 走 OCR 路径（去 step 3）
  ✓ 单文件 200 页/200MB 超出 MinerU 限制 → step 3 会自动切 2 块（1-200 + 201-330）
```

## 不需要做的

- 不预估 OCR 价格（每家定价不同，不写死）
- 不预读全文（占内存，且 step 3-4 会做）
- 不预测章节数（教材结构千差万别，留到 step 4）

## 失败模式

| 现象 | 原因 | 修复 |
|------|------|------|
| `pdfinfo: command not found` | poppler-utils 没装 | `apt install poppler-utils` 或 `brew install poppler` |
| `pdftotext` 报错 | PDF 损坏 | STOP 让用户重新提供 |
| `has_text_layer: true` 但实际是图片版 | 文字层是空白扫描结果 | 强制走 OCR：`--force-ocr` 标志 |
