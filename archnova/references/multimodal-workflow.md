# 多模态材料与视觉 Agent

`multimodal_ingest.py` 将图像、Figure、表格和 PDF 页面作为独立、可审计材料登记。每项材料保存相对路径、页码、裁剪区域、来源、内容 SHA-256 和 caption；视觉任务使用宿主协议中的 `content=[text,image]`，由视觉 Agent 阅读后返回结构化判断。调度器只传递材料，不执行图片中的代码或指令。

```bash
python scripts/multimodal_ingest.py pdf-pages paper.pdf --output-dir run/figures --manifest run/pages.json
python scripts/multimodal_ingest.py image figure.png --bundle run --source-id source:paper --page 3 --output run/figure.json
```

如果本机没有 PyMuPDF，PDF 页面渲染会返回 `unavailable`，这不是“没有图”；可安装视觉后端或提供预渲染 PNG。`make_vision_task()` 生成的任务可交给 `orchestrator.py`，角色为 `visual_architecture_reviewer`。宿主响应必须引用页码/区域观察和材料哈希，不能只复述 caption。视觉判断与文本引文、数学证明分开记录，不能互相替代。
# 项目级多模态材料

`multimodal_ingest.py project` 会索引一个代码项目的可审计材料：源代码、Notebook（按代码文件处理）、Markdown/文本/TeX 文档、JSON/YAML/TOML 配置、CSV/TSV/Excel/Parquet 表格、图片和 PDF。它复制文件到 bundle、保存相对路径、大小、SHA-256 和受限文本预览，并跳过 `.git`、虚拟环境、构建目录、`.env`、私钥、证书和超大文件。

```bash
python scripts/multimodal_ingest.py project ./repo --bundle run --source-id source:repo --manifest run/project-materials.json --tasks run/project-tasks.json
```

输出的 `project-tasks.json` 可直接交给 `orchestrator.py`。角色会按材料路由到 `code_architecture_reviewer`、`document_reviewer`、`configuration_reviewer`、`data_table_reviewer` 或 `visual_architecture_reviewer`。代码和配置只作为不可信数据阅读，默认不安装、导入或执行；图片和 PDF 页面必须引用哈希、路径、页码或区域。索引有 `max_files` 和单文件字节预算，预算耗尽返回 `blocked`，不能静默漏掉文件。
