"""PDF 渲染层：基于 PyMuPDF 将 PDF 页面渲染为高清图片"""
import os
import tempfile

import pymupdf


def page_count(pdf_path: str) -> int:
    """返回 PDF 页数"""
    doc = pymupdf.open(pdf_path)
    try:
        return doc.page_count
    finally:
        doc.close()


def is_text_pdf(pdf_path: str, min_chars_per_page: int = 20) -> bool:
    """判断是否为文本型 PDF（有可提取文本层）。

    抽样前 5 页，平均每页文本字符数 >= min_chars_per_page 视为文本型；
    否则视为扫描件/图片型（需走 OCR）。
    """
    doc = pymupdf.open(pdf_path)
    try:
        pages = doc.page_count
        if pages == 0:
            return False
        sample = min(pages, 5)
        total = sum(len(doc[i].get_text("text").strip()) for i in range(sample))
        return (total / sample) >= min_chars_per_page
    finally:
        doc.close()


def render_page(pdf_path: str, page_index: int, zoom: float = 2.5, out_png: str | None = None) -> str:
    """渲染指定页为 PNG 图片，返回图片路径。

    Args:
        pdf_path: PDF 路径
        page_index: 页码(0 起)
        zoom: 渲染倍率（72*zoom = DPI）
        out_png: 输出路径，None 则用临时文件
    """
    doc = pymupdf.open(pdf_path)
    try:
        page = doc[page_index]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        if out_png is None:
            fd, out_png = tempfile.mkstemp(suffix=".png", prefix="anyocr_page_")
            os.close(fd)
        pix.save(out_png)
        return out_png
    finally:
        doc.close()


def render_pdf_pages(pdf_path: str, zoom: float = 2.5) -> list[str]:
    """渲染整个 PDF，返回所有页 PNG 路径列表"""
    doc = pymupdf.open(pdf_path)
    paths = []
    try:
        mat = pymupdf.Matrix(zoom, zoom)
        for i in range(doc.page_count):
            pix = doc[i].get_pixmap(matrix=mat)
            fd, png = tempfile.mkstemp(suffix=".png", prefix=f"anyocr_p{i}_")
            os.close(fd)
            pix.save(png)
            paths.append(png)
    finally:
        doc.close()
    return paths
