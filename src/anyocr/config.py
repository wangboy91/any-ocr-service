"""全局配置（路径/端口/参数）"""
import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    # ---- 识别参数 ----
    ocr_zoom: float = 2.5            # PDF 页渲染倍率（DPI≈72*zoom）
    min_score: float = 0.45          # RapidOCR 置信度阈值
    line_tolerance: int = 15         # 同一视觉行的 y 容差(px)

    # ---- llama.cpp / VLM ----
    llama_server: str = r"C:\Users\wangb\llamacpp\llama-server.exe"
    model_dir: str = r"C:\Users\wangb\llamacpp\models"
    vlm_model: str = field(default="Qwen2-VL-2B-Instruct-Q4_K_M.gguf")
    vlm_mmproj: str = field(default="mmproj-Qwen2-VL-2B-Instruct-f16.gguf")
    vlm_port: int = 8081             # llama-server 端口
    vlm_ctx_size: int = 4096
    vlm_max_tokens: int = 512
    vlm_timeout: int = 600           # VLM 单次推理超时(秒)

    # ---- API 服务 ----
    api_host: str = "127.0.0.1"
    api_port: int = 8890

    # ---- 代理（模型下载等）----
    proxy: str = field(default_factory=lambda: os.environ.get("HTTPS_PROXY") or "http://127.0.0.1:7897")

    # ---- 模型文件路径 ----
    @property
    def vlm_model_path(self) -> str:
        return os.path.join(self.model_dir, self.vlm_model)

    @property
    def vlm_mmproj_path(self) -> str:
        return os.path.join(self.model_dir, self.vlm_mmproj)

    @property
    def vlm_ready(self) -> bool:
        return os.path.isfile(self.vlm_model_path) and os.path.isfile(self.vlm_mmproj_path)


settings = Settings()
