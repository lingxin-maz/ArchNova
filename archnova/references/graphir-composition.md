# GraphIR 组合与反堆叠验证

ArchNova 的组件组合对象是带契约的 GraphIR，不是层名称列表。组件契约应至少暴露：

- `ports`：具名输入/输出、shape、dtype、layout、state。
- `calculation_contract`：causal、length_preserving、equivariance、extra_state、前后置条件。
- `parameter_specs` 与 `complexity`：参数、时间、显存、KV cache 和通信假设。
- `mutation_surface`：可变参数、可编辑子图、允许作用域和动作。
- provenance/verification：来源快照、实现和验证状态。

GraphIR 有三个视图：

1. 计算骨架：节点、边和类型化张量流。
2. 变异表面：insert、replace、rewire、duplicate_branch、merge、prune 及每步理由。
3. 有效性包络：形状/状态传播、预算、连通性、前后置条件和下游依赖。

`graph_composer.py` 会拒绝类型不兼容、孤立节点、缺少输出路径、预算超限和未经明确契约的 merge；`score_graph()` 输出深度、重复子图、跨分支信息交换和反堆叠惩罚。`ablation_plan()` 为新增节点生成留一必要性测试。

候选搜索应优先使用：LLM 产生语义编辑动作，搜索器维护多样性，静态 GraphIR 验证器把关，短跑/消融/反例收据决定晋级。LLM 不直接生成 PyTorch 作为架构状态。
