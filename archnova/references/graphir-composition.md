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

## 自适应编辑与评估协议

编辑目录不是自由文本 API。`search_protocol.py` 为每个动作绑定作用域、失败模式和修复提示；`validate_edit_action()` 要求动作说明预期的信息流或条件依赖，`diagnose_edit_failure()` 把形状、因果、连通性、预算和重复子图错误归一化为可重试诊断。验证器返回的诊断进入下一轮提议，而不是由 LLM 自行判定通过。

职责固定为：LLM 提议局部编辑并解释机制；搜索器在槽位和岛屿中维护多样性；验证器执行类型、预算、连通性和反堆叠检查；评估器执行同伴组比较、重复种子统计、消融和跨尺度晋升。`decompose_slots()` 把宏观种子拆成有界模块槽位，降低自由编辑造成的随机堆叠。

晋升协议要求所有候选共享问题切片和随机种子，使用修剪均值与组内相对优势；只有同伴评估通过的候选才进入更大规模。每个候选还要和参数量或计算预算匹配的堆叠基线比较，以区分容量增益和结构增益。缺少这些收据时只能标记为设计候选，不能升级为可信架构事实。
