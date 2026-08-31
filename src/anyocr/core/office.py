"""Office 格式解析：docx/pptx/xlsx 直接提取，老格式转换策略。"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class OfficeError(RuntimeError):
    """Office 解析失败。"""


def detect_office_tools() -> dict:
    """探测本机是否有 LibreOffice / soffice（老格式 doc/ppt/xls 转换必需）。"""
    found = {}
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            found[name] = p
    # Windows 常见安装路径兜底
    for cand in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        # 便携版/解压版（msiexec /a 提取）
        r"E:\publicCode\tools\LibreOffice2\program\soffice.exe",
        r"E:\publicCode\tools\LibreOffice\soffice.exe",
    ):
        if Path(cand).exists():
            found.setdefault("soffice", cand)
    return found


# ---------------- DOCX ----------------

def parse_docx(path: Path) -> str:
    """提取 docx 为 Markdown：段落 + 标题样式 + 表格。"""
    try:
        import docx  # python-docx
    except ImportError:
        raise OfficeError("缺少 python-docx，请先 uv add python-docx")
    try:
        d = docx.Document(str(path))
    except Exception as e:
        raise OfficeError(f"docx 打开失败: {e}")

    lines: List[str] = []

    def _iter_blocks(paragraphs, tables):
        """按文档流顺序产出段落与表格（含嵌套表格）。"""
        body = d.element.body
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        for child in body.iterchildren():
            if child.tag.endswith("}p"):
                yield ("p", Paragraph(child, d))
            elif child.tag.endswith("}tbl"):
                yield ("tbl", Table(child, d))

    for kind, obj in _iter_blocks(d.paragraphs, d.tables):
        if kind == "p":
            style = (obj.style.name or "").lower() if obj.style else ""
            text = obj.text.strip()
            if not text:
                continue
            if "heading 1" in style:
                lines.append(f"# {text}")
            elif "heading 2" in style:
                lines.append(f"## {text}")
            elif "heading 3" in style:
                lines.append(f"### {text}")
            elif "list bullet" in style or obj._p.pPr is not None and obj._p.pPr.find(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr"
            ) is not None:
                lines.append(f"- {text}")
            else:
                lines.append(text)
        else:  # table
            md_table = []
            for row in obj.rows:
                cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                md_table.append("| " + " | ".join(cells) + " |")
            if md_table:
                ncol = len(md_table[0].split("|")) - 2
                md_table.insert(1, "|" + "---|" * ncol)
                lines.append("\n".join(md_table))

    if not lines:
        return f"（docx 无正文文本内容，共 {len(d.paragraphs)} 段）"
    return "\n\n".join(lines)


# ---------------- PPTX ----------------

def parse_pptx(path: Path) -> str:
    """提取 pptx 为 Markdown：按 slide 分页，含文本框与表格。"""
    try:
        from pptx import Presentation
    except ImportError:
        raise OfficeError("缺少 python-pptx，请先 uv add python-pptx")
    try:
        prs = Presentation(str(path))
    except Exception as e:
        raise OfficeError(f"pptx 打开失败: {e}")

    slides: List[str] = []
    for idx, slide in enumerate(prs.slides, 1):
        parts: List[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if text:
                    parts.append(text)
            elif shape.has_table:
                tbl = shape.table
                md = []
                for row in tbl.rows:
                    cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                    md.append("| " + " | ".join(cells) + " |")
                if md:
                    ncol = len(md[0].split("|")) - 2
                    md.insert(1, "|" + "---|" * ncol)
                    parts.append("\n".join(md))
            elif getattr(shape, "shape_type", None) is not None and "PICTURE" in str(shape.shape_type):
                parts.append(f"_[图片] {shape.name}_")
        if parts:
            slides.append(f"<!-- Slide {idx} -->\n" + "\n\n".join(parts))

    if not slides:
        return f"（pptx 无正文文本内容，共 {len(prs.slides)} 页）"
    return "\n\n".join(slides)


# ---------------- XLSX ----------------

def parse_xlsx(path: Path) -> str:
    """提取 xlsx 为 Markdown 表格（每个 sheet 一个表格）。"""
    try:
        import openpyxl
    except ImportError:
        raise OfficeError("缺少 openpyxl，请先 uv add openpyxl")
    try:
        wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    except Exception as e:
        raise OfficeError(f"xlsx 打开失败: {e}")

    blocks: List[str] = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        rows = [r for r in rows if any(c is not None and str(c).strip() for c in r)]
        if not rows:
            continue
        blocks.append(f"## Sheet: {ws.title}")
        md = []
        for r in rows:
            cells = ["" if c is None else str(c).replace("\n", " ").replace("|", "\\|") for c in r]
            md.append("| " + " | ".join(cells) + " |")
        ncol = len(md[0].split("|")) - 2
        md.insert(1, "|" + "---|" * ncol)
        blocks.append("\n".join(md))

    if not blocks:
        return f"（xlsx 无有效数据，共 {len(wb.sheetnames)} 个 sheet）"
    return "\n\n".join(blocks)


# ---------------- 老格式转换（doc/ppt/xls） ----------------

def legacy_to_md(path: Path, work_dir: Optional[Path] = None) -> str:
    """老二进制格式 doc/ppt/xls → 转换 → 解析。

    策略：用 LibreOffice headless 转成对应新格式（.docx/.pptx/.xlsx），
    再走上面的解析器。若本机无 LibreOffice 则报错给出安装提示。
    """
    tools = detect_office_tools()
    if not tools:
        raise OfficeError(
            "本机未安装 LibreOffice，无法转换老格式 doc/ppt/xls。\n"
            "请安装 https://www.libreoffice.org/ 后重试（转 docx/pptx 也可先手动另存为新格式）。"
        )
    soffice = tools.get("soffice") or tools.get("libreoffice")
    ext = path.suffix.lower()
    target = {".doc": ".docx", ".ppt": ".pptx", ".xls": ".xlsx", ".rtf": ".docx"}.get(ext)
    if target is None:
        raise OfficeError(f"不支持的老格式: {ext}")

    work_dir = work_dir or (path.parent / f"_conv_{path.stem}")
    work_dir.mkdir(parents=True, exist_ok=True)
    out_file = work_dir / f"{path.stem}{target}"

    cmd = [soffice, "--headless", "--convert-to", target.lstrip("."), "--outdir", str(work_dir), str(path)]
    logger.info("LibreOffice 转换: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        raise OfficeError(f"soffice 启动失败: {soffice}")
    except subprocess.TimeoutExpired:
        raise OfficeError("LibreOffice 转换超时（>180s）")

    if not out_file.exists():
        detail = (proc.stderr or proc.stdout or "").strip()[-500:]
        raise OfficeError(f"LibreOffice 转换失败: {detail}")

    logger.info("转换成功: %s", out_file)
    if target == ".docx":
        return parse_docx(out_file)
    if target == ".pptx":
        return parse_pptx(out_file)
    return parse_xlsx(out_file)


# ---------------- anydoc 引擎（首选，原生支持老格式/ODF/EPUB） ----------------

# anydoc 原生支持的扩展名（docx 系、ppt 系、xls 系、ODF、RTF、EPUB）
_ANYDOC_EXTS = {
    ".doc", ".docx", ".docm",
    ".ppt", ".pps", ".pot", ".pptx", ".pptm", ".ppsx", ".ppsm",
    ".xls", ".xlsx", ".xlsm", ".xlsb",
    ".odt", ".ods", ".odp",
    ".rtf", ".epub",
}


def detect_anydoc() -> bool:
    """anydoc（Firecrawl Rust 引擎）是否可用。"""
    try:
        import anydoc  # noqa: F401
        return True
    except ImportError:
        return False


def anydoc_to_md(path: Path) -> str:
    """用 anydoc 转换 Office/ODF/EPUB → GFM Markdown（本地、毫秒级、输出统一）。"""
    try:
        import anydoc
    except ImportError:
        raise OfficeError("缺少 firecrawl-anydoc，请先 uv pip install firecrawl-anydoc")
    try:
        md = anydoc.to_markdown(str(path))
        if not md or not md.strip():
            raise OfficeError(f"anydoc 输出为空: {path.name}")
        return md
    except OfficeError:
        raise
    except Exception as e:
        raise OfficeError(f"anydoc 转换失败: {type(e).__name__}: {e}")


# ---------------- 总入口 ----------------

def office_to_md(path: Path, work_dir: Optional[Path] = None) -> str:
    """按扩展名路由到对应解析器。返回 Markdown 文本。

    优先 anydoc：原生支持 doc/docx/ppt/pptx/xls/xlsx/rtf/ODF/EPUB，
    统一 GFM 输出、毫秒级；不可用或失败时回退到内置解析器
    （python-docx 等新格式 + LibreOffice 老格式）。
    """
    path = Path(path)  # 兼容 str 入参
    ext = path.suffix.lower()
    # anydoc 优先
    if ext in _ANYDOC_EXTS and detect_anydoc():
        try:
            return anydoc_to_md(path)
        except OfficeError as e:
            logger.warning("anydoc 不可用/失败，回退内置解析: %s", e)
    handlers = {
        ".docx": parse_docx,
        ".pptx": parse_pptx,
        ".xlsx": parse_xlsx,
        ".doc": lambda p: legacy_to_md(p, work_dir),
        ".ppt": lambda p: legacy_to_md(p, work_dir),
        ".xls": lambda p: legacy_to_md(p, work_dir),
        ".rtf": lambda p: legacy_to_md(p, work_dir),
    }
    if ext not in handlers:
        raise OfficeError(f"不支持的 Office 格式: {ext}")
    return handlers[ext](path)
