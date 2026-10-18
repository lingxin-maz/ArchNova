# 神经网络组件素材库

按功能拆解：encoder、decoder、local/global mixing、normalization、position、routing、memory、loss、training 和 compositions。粒度下沉至公式、接口、状态及共享参数；联合模块保留依赖，不能把共享状态拆成互不相干的模型。用 component-schema.json 的完整字段填写 component-library/<group>/<name>/component.json。扩展功能组可自由命名。

组件保留输入输出空间与形状、dtype/layout、状态、参数、公式、离散化、对称性、不变量、稳定条件、复杂度及假设、并行性、替换候选、证据与实现引用。implementation_refs 保存 path/locator/revision/sha256；本地实现可放 implementations/，证据可放 evidence/。不要复制未经许可的整篇材料。provenance.kind 区分 paper_fact、code_observed、derived、proposed，ref 和 locator 指向可核查材料。verified 要求 verification_refs；工具只验证格式，不回放证明或测试。

```bash
python scripts/component_library.py validate component-library/global_mixing/softmax_attention/component.json
python scripts/component_library.py index component-library -o component-library/component-index.json
python scripts/component_retrieval.py --index component-library/component-index.json --query 'attention global' --require constraints.json -o run/candidates.json
```

constraints.json 示例：

```json
{"input_shape":["B","N","D"],"output_shape":["B","N","D"],"state":"none","layout":"BND","invariants":["sequence_length_preserved"]}
```

约束支持 input_shape/output_shape/state/dtype/layout/invariants/functional_group。形状是字面匹配，符号重命名、广播、适配器及状态语义需 AI 检查。不匹配项列在 rejected；缺少元数据不视为满足约束。query 是词项排名，支持标签中的中文词；不能语义推断性能。复杂度按符号表达式存储，当前不自动比较渐近阶数。索引内摘要可检测内部修改；修改组件文件后须重建索引。

随包四个算子为 proposed/unverified 设计素材，未绑定任何论文，不声称已有实现。宿主在素材基础上检索论文和实现，完成来源、参数及测试后才能提升验证状态。检索后交付端口连接、共享状态、适配器、重训需求、函数类变化和最小实验；相同形状不意味着数学等价。


## v1.1 契约升级

所有组件现在显式声明 schema_version=1.1。新增 ports（具名多输入输出、轴、dtype、单位、测度、状态）、state_contract（初始化/更新/重置/梯度策略）、parameter_specs（形状与共享声明）、field_evidence（JSON Pointer → provenance ID）及 verification（验证类型、状态、产物引用和哈希）。旧 interface 保留为粗筛摘要，精确接入以 ports 为准；旧 parameters 是文字说明，parameter_specs 为结构化参数信息。素材中 dtype=float32 是提出的参考配置，不是论文事实。

provenance 每条有 id；paper_fact/code_observed 必须保存快照 sha256。这只能绑定声明的快照，不会自动打开外部 URL 证明支撑关系。verified 的 verification_refs 必须指向已登记的 passed 条目，并且不能含 unknown 类型/状态；它不是测试回放。验证时不信任一个孤立的 verified 字符串。

索引只允许保存在素材库根目录；读取时同时核对原始 component.json。replacement_candidates 必须指向库内存在的组件；外部线索写到检索任务或先登记 unverified 组件。引用的 equations.md、实现和验证文件仍需额外核对其哈希，索引当前只强制重算组件记录本身。

旧组件用显式迁移命令生成待补全草稿：

```bash
python scripts/component_library.py migrate old-component.json -o component.draft.json
```

迁移不会猜多端口和参数形状，不复制 verified 结论；补全并 validate 后才能入库。保留 component-schema-v1.0.json 只用于迁移。

检索新增 ports 和 state_kind 约束，例如：

```json
{"ports":[{"id":"Q","direction":"input","shape":["B","N","D"],"dtype":"float32"}],"state_kind":"stateless"}
```

仍是保守字面匹配，不会解符号形状或证明算子等价。
