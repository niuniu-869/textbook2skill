"""MinerU OCR adapter（最小骨架）

Input:  PDF 路径 + MINERU_TOKEN 环境变量
Output: full markdown 文件路径

三步流程:
1. 申请上传 URL (POST /file-urls/batch)
2. PUT 文件到 OSS
3. 轮询结果 (GET /extract-results/batch/{id}) 直到 done
4. 下载结果 zip + 解压 + 找 full.md

未实现的可扩展点:
- 自动 200 页切块（用 qpdf 切分后并行上传）
- 进度 callback (现在是简单 print)
- 其他 OCR 厂商 (Mistral OCR / Anthropic Files / marker 自部署)

V0 实测踩过的坑:
- OSS 上传慢 ~14KB/s (网络瓶颈)，大文件要切块 + 并发
- state 流转: waiting-file → running → done (含 extract_progress)
- 下载的 zip 里 full.md 在嵌套子目录，要 rglob
"""
import io
import os
import sys
import time
import zipfile
from pathlib import Path
import requests

MINERU_BASE = "https://mineru.net/api/v4"


def request_upload_url(token: str, filename: str, data_id: str = "tx2skill") -> tuple[str, str]:
    """申请 OSS 上传 URL，返回 (batch_id, upload_url)"""
    r = requests.post(
        f"{MINERU_BASE}/file-urls/batch",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "files": [{"name": filename, "data_id": data_id}],
            "model_version": "vlm",
            "is_ocr": True,
            "enable_formula": True,
            "enable_table": True,
            "language": "ch",  # 默认中文，英文教材改成 "en"
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"MinerU 申请上传失败: {data}")
    return data["data"]["batch_id"], data["data"]["file_urls"][0]


def upload_to_oss(upload_url: str, pdf_path: Path) -> None:
    """PUT 文件到 OSS。注意：国内访问慢约 14KB/s"""
    with pdf_path.open("rb") as f:
        r = requests.put(upload_url, data=f, timeout=3600)
    r.raise_for_status()


def poll_until_done(token: str, batch_id: str, interval: int = 30, timeout: int = 7200) -> dict:
    """轮询直到 OCR 完成。Timeout 默认 2h（大书会慢）"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(
            f"{MINERU_BASE}/extract-results/batch/{batch_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"MinerU 查询失败: {data}")
        results = data["data"].get("extract_result", [])
        if results:
            state = results[0].get("state", "")
            progress = results[0].get("extract_progress")
            print(f"[mineru] state={state} progress={progress}", flush=True)
            if state == "done":
                return results[0]
            if state == "failed":
                raise RuntimeError(f"MinerU OCR 失败: {results[0]}")
        else:
            print("[mineru] waiting for results...", flush=True)
        time.sleep(interval)
    raise TimeoutError(f"MinerU OCR 超时（{timeout}s）")


def download_and_extract(zip_url: str, dest_dir: Path) -> Path:
    """下载结果 zip 并解压，返回 full.md 路径"""
    r = requests.get(zip_url, timeout=600)
    r.raise_for_status()
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        zf.extractall(dest_dir)
    md_files = list(dest_dir.rglob("full.md"))
    if not md_files:
        md_files = list(dest_dir.rglob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"未在 {dest_dir} 找到 markdown 输出")
    return md_files[0]


def ocr_pdf(pdf_path: Path, output_dir: Path, token: str | None = None) -> Path:
    """完整 OCR 流程：PDF → markdown 路径"""
    token = token or os.environ.get("MINERU_TOKEN", "")
    if not token:
        raise RuntimeError(
            "MINERU_TOKEN 未设置。请到 https://mineru.net 注册→控制台→API Token，然后:\n"
            "  export MINERU_TOKEN=your-token"
        )
    print(f"[mineru] 申请上传 URL ({pdf_path.name})", flush=True)
    batch_id, upload_url = request_upload_url(token, pdf_path.name, data_id=pdf_path.stem)
    print(f"[mineru] batch_id={batch_id}", flush=True)
    print(f"[mineru] 上传 ({pdf_path.stat().st_size / 1024 / 1024:.1f} MB)...", flush=True)
    upload_to_oss(upload_url, pdf_path)
    print("[mineru] 等待 OCR 完成...", flush=True)
    result = poll_until_done(token, batch_id)
    print("[mineru] 下载结果 zip", flush=True)
    md_path = download_and_extract(result["full_zip_url"], output_dir / batch_id)
    print(f"[mineru] markdown: {md_path}", flush=True)
    return md_path


def split_pdf_for_mineru(pdf_path: Path, max_pages: int = 200) -> list[Path]:
    """如果 PDF 超过 MinerU 200 页限制，用 qpdf 切块。
    返回切块后的 PDF 路径列表（如果不超限，返回 [原文件]）
    """
    import subprocess
    info = subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True, check=True).stdout
    pages_match = [int(x) for x in info.splitlines() if x.startswith("Pages:")]
    if not pages_match:
        return [pdf_path]
    total = int(info.split("Pages:")[1].split("\n")[0].strip())
    if total <= max_pages:
        return [pdf_path]

    output_dir = pdf_path.parent
    parts = []
    for start in range(1, total + 1, max_pages):
        end = min(start + max_pages - 1, total)
        out = output_dir / f"{pdf_path.stem}_p{start}-{end}.pdf"
        subprocess.run(
            ["qpdf", str(pdf_path), "--pages", ".", f"{start}-{end}", "--", str(out)],
            check=True,
        )
        parts.append(out)
    return parts


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: ocr_mineru.py <pdf_path> <output_dir>", file=sys.stderr)
        sys.exit(1)
    pdf = Path(sys.argv[1])
    out = Path(sys.argv[2])
    parts = split_pdf_for_mineru(pdf)
    if len(parts) > 1:
        print(f"[main] PDF > 200 页，切成 {len(parts)} 块", flush=True)
        # 串行 OCR 各块（用户可改并发）
        md_paths = [ocr_pdf(p, out) for p in parts]
        merged = out / "full-merged.md"
        with merged.open("w", encoding="utf-8") as f:
            for mp in md_paths:
                f.write(mp.read_text(encoding="utf-8"))
        print(f"[main] 合并: {merged}", flush=True)
    else:
        ocr_pdf(pdf, out)
