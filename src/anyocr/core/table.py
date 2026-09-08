"""PDF 表格提取：文本型 PDF 用 PyMuPDF find_tables 检测并转 Markdown 表格。

策略：
1. find_tables() 检测页面中的表格（基于网格线/文本对齐），返回 (数据, bbox)
2. 正文 = 页面文本块中「不在表格 bbox 内」的部分（避免表格内容重复）
3. 输出为统一 GFM Markdown 表格
"""
from __future__ import annotations

import logging
from typing import Optional

import pymupdf

logger = logging.getLogger(__name__)


class TableExtractor:
    """文本型 PDF 页面 → 正文 + Markdown 表格。"""

    def __init__(self, min_rows: int = 2, min_cols: int = 1):
        self.min_rows = min_rows   # 少于 2 行不认为是表格
        self.min_cols = min_cols

    # ---------- 表格检测与转换 ----------
    def find_tables(self, page: "pymupdf.Page") -> list[tuple[list[list[str]], object]]:
        """检测一页中的所有表格。

        Returns:
            [(数据(行/列), bbox(Rect)), ...]
        """
        try:
            tables = page.find_tables()
        except Exception as e:
            logger.debug("find_tables 失败: %s", e)
            return []
        result = []
        for t in tables.tables:
            data = self._clean(t.extract())
            if len(data) >= self.min_rows:
                result.append((data, t.bbox))
        return result

    @staticmethod
    def _clean(data: list[list[object]]) -> list[list[str]]:
        """清洗原始单元格：去 None、换行转空格、转义竖线、过滤全空行。"""
        cleaned = []
        for row in data:
            cells = [
                ("" if c is None else str(c).replace("\n", " ").replace("|", "\\|")).strip()
                for c in row
            ]
            if any(cells):  # 丢弃全空行
                cleaned.append(cells)
        return cleaned

    @staticmethod
    def table_to_markdown(data: list[list[str]]) -> str:
        """行列数据 → GFM Markdown 表格。首行作为表头。"""
        if not data:
            return ""
        ncol = max(len(r) for r in data)
        rows = [r + [""] * (ncol - len(r)) for r in data]
        lines = ["| " + " | ".join(rows[0]) + " |"]
        lines.append("|" + "---|" * ncol)
        for r in rows[1:]:
            lines.append("| " + " | ".join(r) + " |")
        return "\n".join(lines)

    @staticmethod
    def _in_bbox(x0, y0, x1, y1, bbox) -> bool:
        """判断文本块是否完全落在表格 bbox 内。兼容 tuple 与 pymupdf.Rect。"""
        bx0, by0, bx1, by1 = bbox[0], bbox[1], bbox[2], bbox[3]
        return x0 >= bx0 and y0 >= by0 and x1 <= bx1 and y1 <= by1

    # ---------- 页级处理：正文(剔除表格区域) + 表格 ----------
    def page_to_markdown(self, page: "pymupdf.Page") -> str:
        """提取一页的 Markdown：正文（表格外文本块）+ 表格（按 bbox 剔除正文重复）。"""
        tables = self.find_tables(page)

        # 正文：文本块过滤，剔除落在表格 bbox 内的块
        body_lines = []
        for b in page.get_text("blocks"):
            if len(b) < 6:
                continue
            x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
            text = text.strip()
            if not text:
                continue
            if any(self._in_bbox(x0, y0, x1, y1, bbox) for _, bbox in tables):
                continue
            body_lines.append(text.replace("\n", " "))

        table_mds = [self.table_to_markdown(data) for data, _ in tables]
        parts = []
        if body_lines:
            parts.append("\n".join(body_lines))
        if table_mds:
            parts.extend(table_mds)
        return "\n\n".join(parts)


def pdf_text_tables_to_md(pdf_path: str, page_limit: Optional[int] = None) -> str:
    """整份文本型 PDF → Markdown（正文 + 表格，表格内容不重复）。失败返回空字符串。"""
    doc = pymupdf.open(pdf_path)
    try:
        extractor = TableExtractor()
        parts = []
        total = doc.page_count if page_limit is None else min(page_limit, doc.page_count)
        for i in range(total):
            page = doc[i]
            md = extractor.page_to_markdown(page)
            if md.strip():
                parts.append(f"<!-- 第{i+1}页 -->\n\n{md}")
        return "\n\n---\n\n".join(parts)
    finally:
        doc.close()
