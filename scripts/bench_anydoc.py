"""anydoc vs any-ocr-service 实测对比（真实文档）。"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

import anydoc
from anyocr.core.engine import AnyOcrEngine

DOCS = [
    ("docx", r"E:\works-doc\北森工作内容\客开\客开\英式股份\英氏DWH接口文档-HR.docx"),
    ("pptx", r"E:\works-doc\北森工作内容\项目管理\绩效继任产品文档\绩效V5算分体系\北森绩效产品算分体系.pptx"),
    ("xlsx", r"E:\works-doc\北森工作内容\绩效云\prodata\performancecloud_systemparam.xlsx"),
]


def timed(fn):
    t0 = time.time()
    out = fn()
    return out, (time.time() - t0) * 1000  # ms


def run_anydoc(path):
    md = anydoc.to_markdown(path)
    return md


def run_anyocr(path):
    return AnyOcrEngine().file_to_md(path)


print("=" * 72)
print(f"{'格式':<6} {'引擎':<18} {'耗时(ms)':>10} {'字符数':>8}  状态")
print("=" * 72)
for fmt, path in DOCS:
    if not os.path.exists(path):
        print(f"{fmt:<6} 文件不存在: {path}")
        continue
    for name, fn in (("anydoc", run_anydoc), ("pdf-ocr", run_anyocr)):
        try:
            out, ms = timed(lambda: fn(path))
            txt = out if isinstance(out, str) else str(out)
            print(f"{fmt:<6} {name:<18} {ms:>10.1f} {len(txt):>8}  OK")
            if name == "anydoc":
                print(f"        └─ 前3行: {txt.strip().splitlines()[:3]}")
        except Exception as e:
            print(f"{fmt:<6} {name:<18} {'-':>10} {'-':>8}  失败: {type(e).__name__}: {str(e)[:80]}")
print("=" * 72)
