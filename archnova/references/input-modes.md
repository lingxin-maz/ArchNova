# 三种输入入口

从 archnova 目录在 Git Bash 执行：

```bash
python scripts/input_modes.py paper-only paper.pdf -o run/plan.json --tasks run/tasks.json --state run/state.json
python scripts/input_modes.py code-only ./repo -o run/code-plan.json --state run/code-state.json
python scripts/input_modes.py paper-and-code --paper paper.pdf --code ./repo -o run/both-plan.json --state run/both-state.json
python scripts/orchestrator.py next run/state.json -o run/request.json
```

paper-only 也接受 HTTP(S) URL，但状态为 retrieval_pending，宿主必须检索并保存原文与哈希后才可作事实判断。DOI/标题需先解析成 URL 或保存为文本文件。输入是本地代码目录、源码文件或 Notebook。拒绝缺失、额外、空目录及超过预算的输入；--max-files 和 --max-bytes 可显式调整。目录指纹覆盖已纳入的材料，忽略依赖、构建目录与符号链接；不代表 Git 全仓库指纹。

两类 reader 独立运行；双来源增加对齐任务；随后拆解算子、理论与仓库检索、组件标准化和索引、候选检索、新架构、替换审查及原型计划。宿主必须实际读取材料，使用 multimodal_ingest/ingest_document 等现有工具，不可仅据任务说明填结果。各任务生成 artifact_path；下游读取上游产物。任务 input_hash 绑定来源快照和任务说明；输入变动需重新生成计划。

提交结果采用 orchestration.md 协议。三种模式可调度、暂停及继续；CLI 只准备工作，不启动模型或训练。缺少论文的模式不能通过旧的论文研究发布门。报告明确分开来源事实、重建、缺口及提案。

核心三任务现有专属 JSON 产物门；提交格式、依赖哈希和验证方法见 operator-design-review.md。其他角色仍由宿主完成并使用通用 envelope，不得将协议回归当作真实 AI 分析能力评测。

可执行分支：增加 --task-spec task.json，固定目标合同并追加实际原型/实验闭环任务。无合同分支改为 prototype_planner，不能再标称原型执行完成。详见 executable-design-loop.md。
