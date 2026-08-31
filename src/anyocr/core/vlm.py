"""llama-server VLM 引擎：加载 Qwen2-VL GGUF，对区域图片做精细识别"""
import base64
import json
import subprocess
import urllib.request

from ..config import settings


class VlmEngine:
    """封装 llama-server 的 VLM 能力（OpenAI 兼容接口）。

    用法:
        vlm = VlmEngine()
        vlm.start()                 # 启动 llama-server（加载 VLM）
        text = vlm.recognize(img)   # 识别图片
        vlm.stop()                  # 停止
    """

    def __init__(self, port: int | None = None):
        self.port = port or settings.vlm_port
        self._proc: subprocess.Popen | None = None
        self._base = f"http://127.0.0.1:{self.port}"

    @property
    def ready(self) -> bool:
        return settings.vlm_ready

    def start(self, wait_timeout: int = 180) -> bool:
        """启动 llama-server 并等待就绪"""
        if not self.ready:
            raise RuntimeError(f"VLM 模型缺失: {settings.vlm_model_path}")
        if self._proc and self._proc.poll() is None:
            return True
        self._proc = subprocess.Popen(
            [
                settings.llama_server, "--model", settings.vlm_model_path,
                "--mmproj", settings.vlm_mmproj_path, "--port", str(self.port),
                "--ctx-size", str(settings.vlm_ctx_size), "--n-gpu-layers", "0",
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return self._wait_ready(wait_timeout)

    def _wait_ready(self, timeout: int) -> bool:
        import time
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                urllib.request.urlopen(f"{self._base}/health", timeout=3)
                return True
            except Exception:
                time.sleep(2)
        return False

    def recognize(self, image_path: str, prompt: str | None = None, max_tokens: int | None = None) -> str:
        """对图片做 VLM 识别，返回文本"""
        if prompt is None:
            prompt = "请识别这张图片中的所有文字内容，按原文顺序输出，不要遗漏。"
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        payload = {
            "model": "qwen2-vl",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            "max_tokens": max_tokens or settings.vlm_max_tokens,
            "temperature": 0,
        }
        req = urllib.request.Request(
            f"{self._base}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=settings.vlm_timeout) as r:
            data = json.load(r)
        return data["choices"][0]["message"]["content"]

    def stop(self):
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
