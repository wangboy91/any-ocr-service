"""命令行入口: anyocr [convert|batch|serve]

用法示例:
    anyocr convert 文档.pdf --out ./out
    anyocr convert 报告.docx --out ./out      # 也支持 pptx/xlsx/doc/ppt/txt 等
    anyocr batch  ./文档目录 --out ./out --vlm
    anyocr serve  --port 8890
"""
import argparse
import glob
import os
import sys
import time

from .core import AnyOcrEngine

# 支持的输入扩展名（batch 扫描时使用）
_SUPPORTED_EXTS = ("*.pdf", "*.docx", "*.pptx", "*.xlsx",
                   "*.doc", "*.ppt", "*.xls", "*.rtf", "*.txt", "*.md")


def _engine(args) -> AnyOcrEngine:
    return AnyOcrEngine()


def cmd_convert(args) -> int:
    eng = _engine(args)
    pdf = args.file
    out = args.out or os.path.dirname(os.path.abspath(pdf))
    base = os.path.splitext(os.path.basename(pdf))[0]
    out_md = os.path.join(out, base + ".md")
    print(f"转换: {pdf}  ->  {out_md}")
    t0 = time.time()
    eng.file_to_md(pdf, out_md=out_md, use_vlm=args.vlm)
    print(f"完成 ({int(time.time()-t0)}s): {os.path.getsize(out_md)} 字节")
    return 0


def cmd_batch(args) -> int:
    eng = _engine(args)
    src = args.path
    if os.path.isdir(src):
        files = []
        for pat in _SUPPORTED_EXTS:
            files.extend(glob.glob(os.path.join(src, pat)))
        files = sorted(set(files))
    else:
        files = [src]
    if not files:
        print("未找到支持的文件（pdf/docx/pptx/xlsx/doc/ppt/xls/rtf/txt/md）")
        return 1
    os.makedirs(args.out, exist_ok=True)
    ok = fail = 0
    for i, p in enumerate(files):
        t0 = time.time()
        base = os.path.splitext(os.path.basename(p))[0]
        try:
            eng.file_to_md(p, out_md=os.path.join(args.out, base + ".md"), use_vlm=args.vlm)
            print(f"[{i+1}/{len(files)}] OK {base[:40]} ({int(time.time()-t0)}s)")
            ok += 1
        except Exception as e:
            print(f"[{i+1}/{len(files)}] FAIL {base[:40]}: {e}")
            fail += 1
    print(f"\n完成: {ok} 成功 / {fail} 失败，输出目录 {os.path.abspath(args.out)}")
    return 0 if fail == 0 else 2


def cmd_serve(args) -> int:
    from .api import run_server
    run_server(host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anyocr", description="多格式 → Markdown 转换服务（PDF OCR + Office 解析）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_conv = sub.add_parser("convert", help="转换单个文件（pdf/docx/pptx/xlsx/doc/ppt/txt/md）")
    p_conv.add_argument("file", help="文件路径")
    p_conv.add_argument("--out", help="输出目录（默认文件所在目录）")
    p_conv.add_argument("--vlm", action="store_true", help="PDF 时启用 VLM 精细识别（需模型已下载）")
    p_conv.set_defaults(func=cmd_convert)

    p_batch = sub.add_parser("batch", help="批量转换（目录或单文件，扫描所有支持格式）")
    p_batch.add_argument("path", help="文件或目录")
    p_batch.add_argument("--out", default="ocr_out", help="输出目录（默认 ocr_out）")
    p_batch.add_argument("--vlm", action="store_true", help="PDF 时启用 VLM 精细识别")
    p_batch.set_defaults(func=cmd_batch)

    p_serve = sub.add_parser("serve", help="启动 HTTP API 服务")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8890)
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
