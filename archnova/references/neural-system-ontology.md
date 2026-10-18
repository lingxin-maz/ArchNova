# 通用神经网络系统架构本体与实时研究

`network_system.py` 将网络建模为五个可审查视图：

- `network_body`：嵌入/编码器、主干层、归一化、注意力、卷积、消息传递、状态空间、扩散去噪、读出/任务头等真正改变函数映射的组件。
- `inference`：KV cache、循环状态、采样器、激活缓存、paged/block 元数据等推理期状态。
- `training`：优化器状态、master weights、梯度、激活保存、损失和反向路径。
- `preprocess`：Tokenizer、图批处理、网格/mesh、数据增强、latent 编码和模态预处理。
- `distributed`：数据并行、ZeRO/FSDP、张量/序列/专家并行、流水线并行、领域分解。

可生成通用 profile：

```bash
python scripts/network_system.py profile --family llm -o llm-system.json
python scripts/network_system.py profile --family neural_operator -o operator-system.json
python scripts/network_system.py validate llm-system.json
```

支持的 family 包括 `llm`、`cnn`、`rnn`、`state_space`、`diffusion`、`gnn`、`neural_operator`、`multimodal` 和 `hybrid`。profile 中的 `proposed` 部件只是结构假设；绑定论文、代码或 runtime 证据后才可改为 `observed` 或 `derived`。

## 实时研究观察

```bash
python scripts/research_watch.py --team openai --team deepmind --team nvidia --since-days 30 --limit 8 -o research-watch.json
```

观察器从 OpenAlex 获取近期候选论文，保存查询时间、endpoint、响应哈希、标题、作者/机构、摘要和架构关键词。关键词只用于候选路由，AI 抽取必须进一步填写 `system_family`、五类视图、证据跨度和不确定性；未完成审查的内容保持 `candidate_requires_ai_review`。

观察器不会把论文摘要自动当作事实，也不会把“大厂团队”标签当作正式作者资格证明。正式结论需要固定论文快照、代码 commit、证据行号和人工或规则复核。

系统 profile 的 lifecycle/state_transitions/interfaces 字段现在可以直接绑定 rank-1..4 runtime、训练、Benchmark、Torch FX lowering 和 replay 收据。
