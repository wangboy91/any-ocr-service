"""RapidOCR 引擎：文本区域检测 + 识别（主通道）"""
import threading
from dataclasses import dataclass

from rapidocr_onnxruntime import RapidOCR

from ..config import settings


@dataclass
class Region:
    """文本区域"""
    box: list            # 四点坐标 [[x,y],...]
    text: str
    score: float

    @property
    def x0(self) -> float: return min(p[0] for p in self.box)
    @property
    def y0(self) -> float: return min(p[1] for p in self.box)
    @property
    def x1(self) -> float: return max(p[0] for p in self.box)
    @property
    def y1(self) -> float: return max(p[1] for p in self.box)


_engine = None
_engine_lock = threading.Lock()


class RapidEngine:
    """RapidOCR 封装（引擎单例，线程安全）"""

    def __init__(self, min_score: float | None = None):
        self.min_score = min_score if min_score is not None else settings.min_score

    @staticmethod
    def _get_engine() -> RapidOCR:
        global _engine
        with _engine_lock:
            if _engine is None:
                _engine = RapidOCR()
            return _engine

    def detect(self, image_path: str) -> list[Region]:
        """检测图片中的文本区域，返回按位置排序的区域列表"""
        engine = self._get_engine()
        result, _ = engine(image_path)
        regions: list[Region] = []
        if not result:
            return regions
        for item in result:
            box, text, score = item
            if score < self.min_score:
                continue
            regions.append(Region(box=box, text=text, score=score))
        # 按 y 行聚类后按 x 排序
        regions.sort(key=lambda r: (round(r.y0 / settings.line_tolerance), r.x0))
        return regions

    def recognize_page(self, image_path: str) -> str:
        """识别整页图片为文本（按视觉行聚类）"""
        regions = self.detect(image_path)
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
