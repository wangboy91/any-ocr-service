# 多格式 → Markdown 转换服务

基于 **anydoc**（Firecrawl Rust 引擎，Office/ODF/EPUB 毫秒级转换）+ **RapidOCR**（PDF 扫描件识别）+ **llama-server / Qwen2-VL**（VLM 精细识别）的多格式文档转 Markdown 服务。
使用 **uv** 管理依赖，分层架构，支持 **CLI** 和 **HTTP API** 双入口。

## 支持的格式

| 类别 | 格式 | 处理方式 | 说明 |
|------|------|----------|------|
| PDF | `.pdf` | 文本型→**文本+表格提取**（毫秒级）；扫描件→**RapidOCR 整页识别**（可选 VLM 精细） | 文本型保结构含表格识别，扫描件走 OCR |
| Word | `.doc` `.docx` `.docm` | **anydoc**（首选）→ 内置解析回退 | 老格式原生解析，不再依赖 LibreOffice |
| PowerPoint | `.ppt` `.pps` `.pot` `.pptx` `.pptm` `.ppsx` `.ppsm` | **anydoc**（首选）→ 内置解析回退 | 含演讲者备注/公式转LaTeX |
| Excel | `.xls` `.xlsx` `.xlsm` `.xlsb` | **anydoc**（首选）→ 内置解析回退 | 合并单元格支持 |
| OpenDocument | `.odt` `.ods` `.odp` | **anydoc** | 新增支持 |
| EPUB | `.epub` | **anydoc** | 新增支持 |
| RTF | `.rtf` | **anydoc**（首选）→ LibreOffice 回退 | |
| 纯文本 | `.txt` `.md` `.csv` | 原样读取 | 无需 OCR |

> anydoc 未安装时自动回退：docx/pptx/xlsx 走内置解析器，老格式 doc/ppt/xls/rtf 走 LibreOffice（可选）。

## 项目结构

```
any-ocr-service/
├── pyproject.toml          # uv 项目配置（依赖/入口）
├── src/anyocr/             # 源码包
│   ├── config.py           # 全局配置（路径/端口/参数）
│   ├── cli.py              # CLI 入口 (anyocr)
│   ├── api.py              # FastAPI 入口 (anyocr-api)
│   └── core/               # 核心引擎层
│       ├── pdf.py          # PDF 渲染 (PyMuPDF)
│       ├── rapid.py        # RapidOCR 引擎（检测+识别）
│       ├── vlm.py          # llama-server VLM 引擎（精细识别）
│       ├── office.py       # Office 解析（docx/pptx/xlsx + 老格式转换）
│       └── engine.py       # 编排引擎（多格式→Markdown 主流程）
├── scripts/                # 辅助脚本
├── docs/                   # 架构文档
└── README.md
```

## 安装

```bash
cd any-ocr-service
uv sync
```

> 若运行时提示 PIL/pydantic 冲突，请清空 PYTHONPATH：
> ```bash
> env -u PYTHONPATH uv run anyocr ...
> ```

## CLI 用法

```bash
# 单文件转换（PDF/Word/PPT/Excel/文本 均可）
uv run anyocr convert 文档.docx --out ./输出目录
uv run anyocr convert 演示.pptx --out ./输出目录

# 批量转换（目录下所有支持的格式）
uv run anyocr batch ./文档目录 --out ./输出目录

# PDF 启用 VLM 精细识别（对低置信度/复杂区域用 Qwen2-VL）
uv run anyocr convert 扫描件.pdf --out ./out --vlm

# 启动 HTTP API
uv run anyocr serve --port 8890
```

## API 用法

```bash
# 启动服务
uv run anyocr serve --port 8890

# 健康检查（含支持格式列表）
curl http://127.0.0.1:8890/health

# 转换（JSON 路径，多格式）
curl -X POST http://127.0.0.1:8890/convert -H "Content-Type: application/json" \
     -d '{"file":"C:/path/x.pptx","out":"C:/out"}'

# 批量
curl -X POST http://127.0.0.1:8890/batch -H "Content-Type: application/json" \
     -d '{"files":["a.pdf","b.docx"],"out":"C:/out"}'

# 文件上传（multipart，浏览器/脚本直接用）
curl -X POST http://127.0.0.1:8890/upload -F "file=@报告.docx" -F "out=C:/out"
```

## 引擎说明

| 引擎 | 职责 | 特点 |
|------|------|------|
| **anydoc** | Office/ODF/EPUB → Markdown（首选） | 纯 Rust 毫秒级、统一 GFM 输出、原生解析老格式 |
| **RapidOCR** | PDF 全页检测 + 识别（主通道） | 快、中文好、纯 CPU |
| **Qwen2-VL**（可选） | 低置信度/表格/复杂区域精细识别 | 准、理解语义，CPU 较慢 |
| **python-docx / pptx / openpyxl** | Office 新格式提取（anydoc 不可用回退） | 保结构 |
| **LibreOffice**（可选） | 老格式转换（anydoc 不可用回退） | 需单独安装 |

VLM 模型（bartowski/Qwen2-VL-2B-Instruct-GGUF）需下载到 `C:\Users\wangb\llamacpp\models\`。

## 商业化路线
详见 [docs/架构设计文档.md](docs/架构设计文档.md)
