"""探测 PDF 元数据（最小骨架）

Input:  PDF 文件路径
Output: probe.json {pages, size_mb, has_text_layer, language, encrypted, needs_ocr}

依赖外部命令: pdfinfo, pdftotext (poppler-utils 包)
"""
import json
import re
import subprocess
import sys
from pathlib import Path


def probe_pdf(pdf_path: Path) -> dict:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    info_out = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True, text=True, check=True
    ).stdout

    pages = _extract_int(info_out, r"^Pages:\s+(\d+)")
    size_bytes = _extract_int(info_out, r"^File size:\s+(\d+)")
    encrypted = "Encrypted:" in info_out and "yes" in info_out.lower()

    # 探测文字层（只看前 5 页避免大文件慢）
    text_out = subprocess.run(
        ["pdftotext", "-l", "5", str(pdf_path), "-"],
        capture_output=True, text=True
    ).stdout
    text_chars = len(text_out.strip())
    has_text_layer = text_chars > 1000  # 阈值经验值

    # 简单语言探测：是否含中文字符
    has_chinese = bool(re.search(r"[一-鿿]", text_out))
    language = "ch" if has_chinese else "en"

    return {
        "path": str(pdf_path.absolute()),
        "pages": pages or 0,
        "size_mb": round((size_bytes or 0) / 1024 / 1024, 2),
        "has_text_layer": has_text_layer,
        "language": language,
        "encrypted": encrypted,
        "needs_ocr": not has_text_layer and not encrypted,
    }


def _extract_int(text: str, pattern: str) -> int:
    m = re.search(pattern, text, re.MULTILINE)
    return int(m.group(1)) if m else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: probe.py <pdf_path>", file=sys.stderr)
        sys.exit(1)
    result = probe_pdf(Path(sys.argv[1]))
    print(json.dumps(result, indent=2, ensure_ascii=False))
