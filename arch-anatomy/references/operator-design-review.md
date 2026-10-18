# 算子拆解、新架构与替换审查契约

三个核心任务输出 `assets/architecture-task.schema.json`，用 `scripts/task_contracts.py validate` 校验。`input_modes.py` 把契约绑定到任务，调度器在 completed 前强制执行。任务 envelope 使用真正的 `host-response.schema.json`，不再是字段说明文字。artifact_path 相对路径按 state.json 所在目录解释，推荐绝对路径。产物内 input_hash 必须复制当前任务值；上游核心产物的 task_id/sha256 写入 upstream_artifacts。调度器保存产物 SHA-256，续跑时检测修改，替换审查的 dataflow 必须与直接上游设计一致。

## 算子拆解

从两份独立的论文/代码图开始，不能按模型名直接套模板。拆到可解释的 primitive 或明确 composition；每个 operators 项写公式、定义域、离散化、component_id、证据和复杂度假设，给出覆盖范围、排除项与停止细分理由。识别参数共享、缓存、归一化轴、边界/掩码、训练/推理分支及梯度路径。无法确认的控制流、动态形状和源码调用放进 unresolved。

图沿用 anatomy 的 port/edge/dataflow 定义和校验器：所有 operator 都有节点与端口，输入单一生产者，边方向及形状/轴/dtype/单位/测度/状态逐项相符；适配器显式建节点；循环只允许延迟状态边。算子注册到组件库前，另外运行 component_library.py validate/index。component_id 在任务草稿中可指向计划新增的组件；当前不自动证明实现与公式一致。

## 新架构设计

先定义任务约束和简单可比 baseline，给出瓶颈机制，再比较至少两个结构上不同的候选，解释保留/排除原因。最终产物只保留一张完整图：共享隐状态、共享参数和跨物理场耦合不能被拆成没有连接的子模型。为每个替换写清函数类变化、适配器、归一化/尺度、初始化、训练目标和推理成本。不得只增加模块名字或把“形状相同”写成等价。

JSON 强制 baseline、objectives、affected_parts、changes_shared_parameters、cost_predictions 和 experiment。成本使用受限算术表达式与带单位变量；返回值与声明单位必须一致且非负，不能执行函数或任意 Python。符号 O(...) 仍写到组件 complexity；数值预测是给定工况下的估计，不是实测。至少记录一个成本量；延迟和显存需真实 benchmark。

experiment 强制独立数据划分、共同预算、至少两种种子、消融、可判定 kill_criterion 和机器可计算 decision_rule/metric_definition。规则复用 numeric_checks 的单位和条件验证，无观测时返回 pending。executed 必须登记 receipt_refs；实际收据回放继续使用 experiment_runner 和研究发布门，契约验证不会将引用自动升级为实验成功。

## 替换审查

逐项检查 interface、function_class、state、causality、symmetry、stability、precision、gradient、cost、sharing、training。每项都写条件、判断和证据；不适用也说明原因。relation 区分接口、精确等价、近似、新函数类和未知；domain/parameter_mapping 不可缺。精确等价需要 derived 证据，仍须 semantic_review/proof_checks 做独立推导审查。

admit 要求无 unresolved、无 unknown/violated 项、无图告警，且不能只引用 proposed 素材。违反项只可 reject 或写明条件后 conditional。完成审查不等于通过审查：unresolved/reject 也可以完成审查任务，下游只能生成修订或验证计划，不能宣称候选已获准用于正式实验。conditional 先解决条件，才能升级结论。

## 示例与验证

```bash
python scripts/task_contracts.py example decomposition -o run/decomposition.example.json
python scripts/task_contracts.py example design -o run/design.example.json
python scripts/task_contracts.py example replacement_review -o run/review.example.json
python scripts/task_contracts.py validate run/design.example.json --kind design
```

样例是合成 identity 图，只展示格式，不代表真实科研任务。真实任务替换 input_hash、图、算子和证据，不得复制样例当成果。schema 的图定义与 anatomy 生成产物有一致性回归；后续本体更新必须同步任务契约。

## 已知边界

现在验证的是记录结构、引用关系、声明图和受限数值表达式。任意公式、函数空间、稳定性证明和一般数学等价仍需语义审查；源码真实执行图不由 JSON 自行恢复。除核心三任务外，reader/scout/retriever 等仍使用通用宿主 envelope，没有专属完整结果 schema。符号维度统一、自动微分探针、数据集训练、性能提升及 AI 判断准确率未在这次开发中测得。


## 真实材料分析中的逐调用覆盖核对

拆解先按完整 forward 路径列出调用表，再对每个调用登记“已拆为节点/明确合并且有理由/不在当前配置/材料缺失”。相同模块被调用多次要区分 invocation；构造函数可证明模块属性，调用位置证明它确实在当前路径执行。复合表达式应逐项核对投影、布局、乘积、缩放、mask、归一化、dropout、聚合及读出；谱路径需核对频率裁剪、未写频率、轴约定、逆变换目标尺寸与偏置。不得把父模型论文中的支路直接加到子模块计算图。

引用源文件给出的原始行号，不自行按截取片段重编号；每个事实给窄锚点，并说明行号是构造还是调用。只提供论文时使用操作模板，明确 head/layer/site 的重复粒度，不能拿模板数与代码逐次调用数直接比较。遇到歧义先列标注争议，不能调参考答案以追求分数。

## 放行与范围

admit 时 interface/function_class 两项必须 satisfied，不能 not_applicable；其他 not_applicable 项也必须有证据说明为什么不适用。精确等价的每条 proof_evidence 都必须是 derived。此门仍只检查声明和引用类型，不证明推导正确：给出精确适用域、训练/推理模式、精度、参数映射、观察量，以及最小反例或证明草图。不能用“相同形状”、单次输出、API 名字相似或 irrelevant derivation 背书。

对安全重写不要一律拒绝：明确限定的 eval-only dropout 去除、无别名观测的分配方式变化等，应按各自范围检查；训练语义、存储别名、精度或性能超出范围就保留 unknown。真实评测分别报告错误放行与安全正例召回，避免全拒绝策略。

微操作口径补充：显式代数转置与乘法分别登记；split/concat/view/transpose 统一视作布局族并保留具体操作名，contiguous 视作存储/物化操作，避免用 other 与 reshape 的任意选择制造评分差异。证据覆盖每一段实际提供的行，不能仅检查起止行和长度。功能口径允许组合，但需明确组合边界；不得据已见题目的评分结果反向修改冻结参考。
