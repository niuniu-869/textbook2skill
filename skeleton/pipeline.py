"""端到端编排器（最小骨架）

把 step 2-7 串起来。Step 1 (问用户) 和 Step 8 (安装) 是交互式的，不在这里跑。

用法:
    python3 pipeline.py \\
        --pdf /path/to/book.pdf \\
        --skill-name gao-cai \\
        --book-title "高级管理会计理论与实务" \\
        --output /tmp/textbook2skill-build \\
        --prompts /path/to/textbook2skill/prompts \\
        --ocr-provider mineru \\
        --llm-provider deepseek \\
        [--ocr-cache <markdown_path>]   # 跳过 OCR 用现有 markdown
        [--skip-bench]                   # 跳过 benchmark（不推荐）

环境变量:
    MINERU_TOKEN  (扫描版 PDF 必需)
    DEEPSEEK_KEY  或对应 LLM 厂商的 key
"""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from probe import probe_pdf
from split import split_chapters, extract_toc
from extract import extract_all
from assemble import assemble
from llm import LLMClient


def run_pipeline(args):
    work = args.output
    work.mkdir(parents=True, exist_ok=True)

    # ---- Step 2: probe ----
    print("\n=== [2] PROBE ===", flush=True)
    probe = probe_pdf(args.pdf)
    print(json.dumps(probe, indent=2, ensure_ascii=False))
    (work / "probe.json").write_text(json.dumps(probe, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- Step 3: OCR ----
    print("\n=== [3] OCR ===", flush=True)
    if args.ocr_cache and args.ocr_cache.exists():
        print(f"使用 OCR 缓存: {args.ocr_cache}", flush=True)
        markdown_path = args.ocr_cache
    elif probe["needs_ocr"]:
        if args.ocr_provider == "mineru":
            from ocr_mineru import ocr_pdf, split_pdf_for_mineru
            parts = split_pdf_for_mineru(args.pdf)
            if len(parts) > 1:
                print(f"PDF > 200 页，切成 {len(parts)} 块", flush=True)
                md_paths = [ocr_pdf(p, work / "ocr") for p in parts]
                markdown_path = work / "ocr" / "full-merged.md"
                with markdown_path.open("w", encoding="utf-8") as f:
                    for mp in md_paths:
                        f.write(mp.read_text(encoding="utf-8"))
            else:
                markdown_path = ocr_pdf(args.pdf, work / "ocr")
        else:
            raise NotImplementedError(
                f"OCR provider '{args.ocr_provider}' not implemented in skeleton. "
                "扩展方式: 在 skeleton/ 加 ocr_<provider>.py"
            )
    else:
        # 有文字层，直接 pdftotext
        import subprocess
        markdown_path = work / "book.md"
        subprocess.run(
            ["pdftotext", str(args.pdf), str(markdown_path)],
            check=True,
        )
        print(f"PDF 有文字层，pdftotext → {markdown_path}", flush=True)

    markdown = markdown_path.read_text(encoding="utf-8")
    print(f"markdown 长度: {len(markdown)} 字符", flush=True)

    # ---- Step 4: split ----
    print("\n=== [4] SPLIT ===", flush=True)
    chapters = split_chapters(markdown)
    chapters_json = [asdict(c) for c in chapters]
    (work / "chapters.json").write_text(
        json.dumps(chapters_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"识别 {len(chapters)} 章 (策略: {chapters[0].source_strategy if chapters else 'NA'})", flush=True)
    for c in chapters[:5]:
        print(f"  [{c.idx}] {c.title[:50]} ({len(c.content)} chars)", flush=True)
    if len(chapters) < 3:
        print("⚠️  章节数过少 (< 3)，建议 STOP 让用户检查 OCR 输出", flush=True)
        if not args.force:
            sys.exit(1)

    # ---- Step 5: extract ----
    print("\n=== [5] EXTRACT ===", flush=True)
    client = LLMClient.from_env(args.llm_provider)
    extracted_dir = work / "extracted"
    extract_all(chapters_json, extracted_dir, client, args.prompts)

    # ---- Step 6: assemble ----
    print("\n=== [6] ASSEMBLE ===", flush=True)
    skill_dir = work / "skill"
    assemble(extracted_dir, skill_dir, args.skill_name, args.book_title)

    # ---- Step 7: bench ----
    if args.skip_bench:
        print("\n⚠️  跳过 benchmark — 不推荐！没有 benchmark 你不知道 skill 是不是真有用", flush=True)
    else:
        print("\n=== [7] BENCHMARK ===", flush=True)
        from bench import gen_questions, run_benchmark
        # 默认 allocation：各章按 token 量比例分，总 30 题
        allocation = _allocate(chapters_json, total=30)
        print(f"题目分配: {allocation}", flush=True)
        questions = gen_questions(chapters_json, allocation, client, args.prompts)
        questions_path = work / "benchmark-questions.json"
        questions_path.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"出题 {len(questions)} 道 → {questions_path}", flush=True)
        run_benchmark(skill_dir, questions, client, args.prompts,
                      output_path=work / "benchmark.json")

    print("\n=== DONE ===", flush=True)
    print(f"Skill 目录: {skill_dir}", flush=True)
    print(f"下一步: 复制到 ~/.claude/skills/{args.skill_name}/ (见 step 8)", flush=True)


def _allocate(chapters: list[dict], total: int = 30) -> dict[str, int]:
    """按章节 token 量比例分配题目数"""
    weights = [(c["idx"], len(c["content"])) for c in chapters]
    total_weight = sum(w for _, w in weights)
    allocation = {}
    for idx, w in weights:
        prefix = f"{idx:02d}-第{idx}章"
        n = max(1, round(total * w / total_weight))
        allocation[prefix] = n
    # 总数对齐到 total
    diff = total - sum(allocation.values())
    if diff != 0:
        # 简单调整最大章节
        max_key = max(allocation, key=lambda k: allocation[k])
        allocation[max_key] = max(1, allocation[max_key] + diff)
    return allocation


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--skill-name", required=True)
    p.add_argument("--book-title", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--prompts", type=Path, required=True,
                   help="textbook2skill/prompts/ 目录路径")
    p.add_argument("--ocr-provider", default="mineru")
    p.add_argument("--llm-provider", default="deepseek")
    p.add_argument("--ocr-cache", type=Path, help="如已有 OCR markdown 文件，直接用，跳过 OCR")
    p.add_argument("--skip-bench", action="store_true")
    p.add_argument("--force", action="store_true", help="即使 split 章节过少也继续")
    args = p.parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
