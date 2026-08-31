"""核心引擎层：PDF渲染 / OCR引擎 / VLM识别 / 编排"""
from .pdf import render_page, page_count
from .rapid import RapidEngine, Region
from .vlm import VlmEngine
from .engine import AnyOcrEngine

__all__ = ["render_page", "page_count", "RapidEngine", "Region", "VlmEngine", "AnyOcrEngine"]
