"""识别引擎编排层：PDF → Markdown

主流程: PDF 渲染 → RapidOCR 整页识别；可选 VLM 对低置信度/表格区域精细识别
"""
import logging
import os
import re

from ..config import settings
from .office import office_to_md
from .pdf import render_pdf_pages, is_text_pdf
from .rapid import RapidEngine, Region
from .table import pdf_text_tables_to_md
from .vlm import VlmEngine

logger = logging.getLogger(__name__)

# 直接解析（无需 OCR）的文本类格式
_TEXT_EXTS = {".txt", ".md", ".markdown", ".csv"}
# Office 文本格式（anydoc 优先 + 内置解析兜底）
_OFFICE_EXTS = {
    ".docx", ".pptx", ".xlsx", ".doc", ".ppt", ".xls", ".rtf",
    # anydoc 扩展支持
    ".docm", ".pps", ".pot", ".pptm", ".ppsx", ".ppsm", ".xlsm", ".xlsb",
    ".odt", ".ods", ".odp", ".epub",
}


class AnyOcrEngine:
    """PDF → Markdown 引擎（RapidOCR 主通道 + 可选 VLM 精细通道）"""

    def __init__(self, rapid: RapidEngine | None = None, vlm: VlmEngine | None = None):
        self.rapid = rapid or RapidEngine()
        self.vlm = vlm or VlmEngine()
        self._vlm_started = False

    # ---------- 核心转换 ----------
    def pdf_to_md(self, pdf_path: str, out_md: str | None = None,
                  use_vlm: bool = False, vlm_pages: list[int] | None = None) -> str:
        """转换 PDF 为 markdown 文本。

        Args:
            pdf_path: PDF 路径
            out_md: 输出 md 路径（None 则仅返回文本）
            use_vlm: 是否对低置信度区域启用 VLM 精细识别
            vlm_pages: 指定启用 VLM 的页码（None = 所有页低置信度区域）
        """
        pdf_path = os.path.abspath(pdf_path)
        base = os.path.splitext(os.path.basename(pdf_path))[0]

        # 文本型 PDF：直接提取文本+表格（快、保结构），无需 OCR
        if is_text_pdf(pdf_path):
            try:
                md = pdf_text_tables_to_md(pdf_path)
                if md and md.strip():
                    md = (f"# {base}\n\n> 由 any-ocr-service 文本提取（含表格识别）\n\n"
                          + md)
                    if out_md:
                        os.makedirs(os.path.dirname(os.path.abspath(out_md)), exist_ok=True)
                        with open(out_md, "w", encoding="utf-8") as f:
                            f.write(md)
                    return md
            except Exception as e:
                logger.warning("PDF 文本提取失败，回退 OCR: %s", e)

        # 扫描件/图片型 PDF：OCR 通道（RapidOCR 主通道 + 可选 VLM 精细）
        page_pngs = render_pdf_pages(pdf_path, zoom=settings.ocr_zoom)
        page_texts = []
        try:
            for i, png in enumerate(page_pngs):
                regions = self.rapid.detect(png)
                # VLM 精细识别（可选）：低置信度区域
                if use_vlm and settings.vlm_ready and (vlm_pages is None or i in vlm_pages):
                    if not self._vlm_started:
                        self.vlm.start()
                        self._vlm_started = True
                    regions = self._refine_with_vlm(png, regions)
                text = self._regions_to_text(regions)
                if text.strip():
                    page_texts.append(f"<!-- 第{i+1}页 -->\n\n{text}")
        finally:
            for p in page_pngs:
                try: os.remove(p)
                except OSError: pass

        md = (f"# {base}\n\n> 由 any-ocr-service (RapidOCR"
              + (" + Qwen2-VL" if use_vlm else "") + ") 生成\n\n"
              + "\n\n---\n\n".join(page_texts))
        if out_md:
            os.makedirs(os.path.dirname(os.path.abspath(out_md)), exist_ok=True)
            with open(out_md, "w", encoding="utf-8") as f:
                f.write(md)
        return md

    # ---------- 多格式入口 ----------
    def file_to_md(self, file_path: str, out_md: str | None = None,
                   use_vlm: bool = False, vlm_pages: list[int] | None = None) -> str:
        """按扩展名自动路由：PDF→OCR；Office→直接解析；txt/md→原样。

        Args:
            file_path: 任意支持的文件（pdf/docx/pptx/xlsx/doc/ppt/xls/txt/md）
            out_md: 输出 md 路径（None 则仅返回文本）
            use_vlm: PDF 时是否启用 VLM 精细识别
            vlm_pages: PDF 时指定启用 VLM 的页码
        """
        ext = os.path.splitext(file_path)[1].lower()
        base = os.path.splitext(os.path.basename(file_path))[0]

        if ext == ".pdf":
            md = self.pdf_to_md(file_path, out_md=out_md, use_vlm=use_vlm, vlm_pages=vlm_pages)
            return md
        if ext in _TEXT_EXTS:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            md = f"# {base}\n\n> 由 any-ocr-service 直接读取\n\n{content}"
        elif ext in _OFFICE_EXTS:
            md = office_to_md(file_path)
            md = f"# {base}\n\n> 由 any-ocr-service ({ext[1:]} 解析) 生成\n\n{md}"
        else:
            raise ValueError(f"不支持的文件格式: {ext}（支持 pdf/docx/pptx/xlsx/doc/ppt/xls/rtf/txt/md）")

        if out_md:
            os.makedirs(os.path.dirname(os.path.abspath(out_md)), exist_ok=True)
            with open(out_md, "w", encoding="utf-8") as f:
                f.write(md)
        return md

    # ---------- 内部工具 ----------
    def _refine_with_vlm(self, page_png: str, regions: list[Region]) -> list[Region]:
        """对低置信度区域用 VLM 重新识别"""
        from PIL import Image
        refined = []
        img = Image.open(page_png)
        for r in regions:
            if r.score >= 0.85 or (r.x1 - r.x0) * (r.y1 - r.y0) < 200:
                refined.append(r)  # 高置信度或过小区域直接用 RapidOCR
                continue
            crop = img.crop((max(0, r.x0-10), max(0, r.y0-10), r.x1+10, r.y1+10))
            tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "vlm_crop.png")
            crop.save(tmp)
            try:
                text = self.vlm.recognize(tmp)
                if text.strip():
                    refined.append(Region(box=r.box, text=text.strip(), score=1.0))
                    continue
            except Exception:
                pass
            refined.append(r)
        return refined

    @staticmethod
    def _regions_to_text(regions: list[Region]) -> str:
        """区域按视觉行聚类为文本"""
        merged: list[tuple[float, float, str]] = []
        for r in regions:
            if merged and abs(merged[-1][0] - r.y0) < settings.line_tolerance:
                if r.x0 > merged[-1][1]:
                    merged[-1] = (merged[-1][0], merged[-1][1], merged[-1][2] + " " + r.text)
                else:
                    merged[-1] = (merged[-1][0], merged[-1][1], r.text + " " + merged[-1][2])
            else:
                merged.append((r.y0, r.x0, r.text))
        return "\n".join(m[2] for m in merged)
