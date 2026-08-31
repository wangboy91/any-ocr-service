"""HTTP API 服务: FastAPI

启动:  anyocr serve  (或 python -m anyocr.api)
端点:
    GET  /health                健康检查
    POST /convert               转换单个文件（多格式）
         JSON:  {"file": "C:/abs/x.docx", "out": "C:/out", "use_vlm": bool}
         multipart: 上传文件 + out/use_vlm 表单字段
    POST /batch     {"files": [...], "out": "C:/out"}
"""
import os
import tempfile
import time

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import settings
from .core import AnyOcrEngine, VlmEngine, Region

app = FastAPI(title="any-ocr-service", version="0.3.0")

# 引擎（模型常驻，复用）
_engine = AnyOcrEngine()
_engine_lock_owner = "single"  # 简化：单 Worker 部署


class ConvertRequest(BaseModel):
    file: str
    out: str | None = None
    use_vlm: bool = False
    save_md: bool = True


class BatchRequest(BaseModel):
    files: list[str]
    out: str | None = None
    use_vlm: bool = False


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "any-ocr-service",
        "formats": "pdf/docx/pptx/xlsx/doc/ppt/xls/rtf/txt/md",
        "rapidocr": "ready",
        "vlm": {"ready": settings.vlm_ready, "model": settings.vlm_model},
    }


@app.post("/convert")
def convert(req: ConvertRequest):
    if not os.path.exists(req.file):
        return JSONResponse({"ok": False, "error": f"文件不存在: {req.file}"}, status_code=404)
    try:
        t0 = time.time()
        out_md = None
        if req.save_md and req.out:
            base = os.path.splitext(os.path.basename(req.file))[0]
            out_md = os.path.join(req.out, base + ".md")
        md = _engine.file_to_md(req.file, out_md=out_md, use_vlm=req.use_vlm)
        return {"ok": True, "file": req.file, "md": md, "md_path": out_md,
                "seconds": round(time.time() - t0, 1)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/upload")
async def upload(file: UploadFile = File(...),
                 out: str | None = Form(None),
                 use_vlm: bool = Form(False),
                 save_md: bool = Form(True)):
    """multipart 文件上传转换（浏览器/脚本直接用）。"""
    tmp_dir = tempfile.mkdtemp(prefix="anyocr_up_")
    tmp_path = os.path.join(tmp_dir, file.filename)
    content = await file.read()
    with open(tmp_path, "wb") as f:
        f.write(content)
    try:
        t0 = time.time()
        out_md = None
        if save_md and out:
            base = os.path.splitext(file.filename)[0]
            out_md = os.path.join(out, base + ".md")
        md = _engine.file_to_md(tmp_path, out_md=out_md, use_vlm=use_vlm)
        return {"ok": True, "file": file.filename, "md": md, "md_path": out_md,
                "seconds": round(time.time() - t0, 1)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    finally:
        try:
            os.remove(tmp_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass


@app.post("/batch")
def batch(req: BatchRequest):
    results = []
    for p in req.files:
        try:
            t0 = time.time()
            out_md = None
            if req.out:
                base = os.path.splitext(os.path.basename(p))[0]
                out_md = os.path.join(req.out, base + ".md")
            md = _engine.file_to_md(p, out_md=out_md, use_vlm=req.use_vlm)
            results.append({"file": p, "ok": True, "md_path": out_md,
                            "chars": len(md), "seconds": round(time.time() - t0, 1)})
        except Exception as e:
            results.append({"file": p, "ok": False, "error": str(e)})
    return {"ok": True, "results": results}


def run_server(host: str | None = None, port: int | None = None):
    import uvicorn
    host = host or settings.api_host
    port = port or settings.api_port
    print(f"any-ocr-service 启动: http://{host}:{port}  (VLM {'就绪' if settings.vlm_ready else '未就绪'})")
    uvicorn.run(app, host=host, port=port)


def main():
    run_server()


if __name__ == "__main__":
    main()
