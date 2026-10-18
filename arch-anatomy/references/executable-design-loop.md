# 目标绑定的可执行设计闭环

这条路径把“设计文档”推进到实际程序与有限实验。它与旧论文研究发布门并行：支持范围内可以执行，不支持的算子/状态/物理单位必须保持 blocked，不能把计划写成已执行成果。

## 1. 完整声明对象绑定

`architecture_ir.artifact_semantics` 包含 operators、dataflow、runtime_ir、task_spec_hash。替换审查必须与上游设计逐项相同，改公式、参数、连线、状态或目标摘要都会失配。此摘要是“审查对象相同”的保证，不是数学等价证明；即便同一公式，不同精度/初始条件的普遍正确性仍需实际审查。

有 `--task-spec` 的设计/审查要求 runtime_ir，算子 component_id=`runtime:<op>`、equation=`node_equation(node)` 及图由运行 IR 导出。声明图不能与执行模型各写一份互不相干的数据。参数引用统一到 parameters[].id，同一 ID 被多节点使用即共享同一数值参数。JSON 中的参数值、trainable 标记、dtype、输入输出和每个节点 attributes 都参与模型摘要。

## 2. 固定目标合同

`assets/task-spec.schema.json` 固定 goal、输入输出、符号维度、允许算子、非负输出要求、节点/参数/候选预算、mse/max_abs_error 阈值和最小改进，以及数据文件 SHA-256。

```bash
python scripts/task_spec.py assets/design-loop-example/task.json
python scripts/input_modes.py code-only ./repo --task-spec task.json -o run/plan.json --state run/state.json
```

目标 hash 绑定到下游每个任务。提交和续跑时重新读取合同、校验数据；目标或数据变化则阻塞，不能为了候选通过而修改阈值。开发/留出样本强制分别存在，拒绝完全相同输入跨拆分重复。此检查不能发现所有统计泄漏；划分仍需研究者合理设计。

不带 task_spec 的旧入口现在以 prototype_planner 结束，明确只产出未执行计划。带合同的路径增加 prototype_generator → experiment_loop，两者必须提供可验证文件。审查 admit 才能提交已完成原型；conditional/reject/unresolved 只能产生修订计划或 blocked，不以完成状态冒充许可。

## 3. 支持的可执行算子

当前参考运行时限于维度为 1..64 的 rank-1..4、实数、无量纲张量；参数仍为有界二维矩阵，使用 Python 双精度标量算术；支持 identity、scale、relu、tanh、linear、add、matmul、transpose、softmax、reshape、concat、layernorm。linear 定义为 X@W，bias 只能显式为 [1,output_width]；add 要求完全同形，不隐式广播。检查符号绑定、权重维度、未知算子、死节点、预算和外部 I/O。

它是受限参考网络运行器；softmax、transpose、matmul 可以表达未融合的注意力数据流，但尚未提供 fused attention、卷积、循环状态、复数或动态控制流。训练已支持 development split 上的有界矩阵参数有限差分 SGD，但仍不是自动微分、反向传播、GPU 或分布式训练。PyTorch/JAX 图恢复仍需审查过的隔离 lowering，不会自动导入任意代码。

## 4. 实际原型文件

```bash
python scripts/prototype_builder.py build --model model.json --task task.json -o run/prototype
python scripts/prototype_builder.py verify run/prototype/prototype.json
```

每个 bundle 包含 adapter.py、engine.py、model.json、task_spec.json、dataset.json、prototype.json。验证所有文件哈希，并要求 adapter/engine 与当前受支持生成器一致。修改模型后即使只更新 manifest 摘要，也无法换成任意隐藏运行代码。适配器只取 inputs 计算输出，不读取 targets；数据随包用于回放，受限引擎不会把标签当预测。

通过宿主任务提交时，build 加 `--input-hash TASK_HASH --upstream upstream.json`。upstream 数组从 request.dependency_artifacts 复制 task_id/sha256。实际原型还必须与上游审查的 runtime_ir 完全一致。

## 5. 失败—修订—实验闭环

```bash
python scripts/design_loop.py run --task assets/design-loop-example/task.json --initial assets/design-loop-example/initial.json -o run/demo --execute
python scripts/design_loop.py replay run/demo/result.json
```

没有 --execute 就只构建 planned 产物，不声称已执行实验。实际执行复用 experiment_runner：固定参考适配器与候选适配器分别产生原始 JSON，检查响应哈希并重算指标。参考适配器返回题目 targets 作为独立对照；生成的候选适配器不能读取它们。

初始候选开发目标失败后才生成结构修订。v1 提供 relu 输出修复和 absolute 正负双分支修复；规则只接收模型与目标合同，不接收任何开发/留出标签。它们是明确登记的有限假设，不是 AI 自动发现新原理，也不保证有益。可配置规则顺序，重复摘要去重，先按形状/预算筛选，再执行开发评估。

开发标准包括固定最大误差、最小改进和样本非负条件。失败记录全部保存；候选预算耗尽则 budget_exhausted，无可行候选则 no_viable_candidate。一个候选通过开发后，锁定它并仅做一轮留出比较；留出失败则 holdout_failed，绝不继续试下一候选或放宽目标。初始模型与最终候选使用同一留出数据和指标；没有随机训练，不能虚构多种子统计。

replay 从原始参考/候选响应、固定数据和模型重新计算每次指标、约束及决策，检查实际生成程序依赖、候选修订来源和语义摘要。它会拒绝改阈值、换模型、改结果或省略失败尝试。局部自记收据不能防止完全伪造整个历史，不是外部执行认证。

文件调度里的 experiment_loop 使用 `--input-hash` 与 `--upstream` 绑定上一任务。任务 completed 仅表示实验记录完成，result.status=accepted 才表示声明样本和预算下通过目标。accepted 不是普遍等价、泛化优势或新架构创新证明。

## 6. 旧实验记录的修复

architecture-task 的 experiment.status=executed 不再只凭非空 receipt_refs 放行。必须指定 bundle_root，实际解析文件、校验适配器依赖、核对目标完整语义摘要，并 replay 原始响应。命令行 `task_contracts.py validate` 可加 --task-spec 和 --bundle。

闭环使用独立 design_loop 产物，因为“输出是否等于参考”和“误差是否达到任务目标”是不同判定。某次对照 receipt.status=failed 可能只表示和标签不完全相等；任务指标重算后仍需独立判断阈值，不能复制 passed 字段当目标达成。

## 7. 验证边界

随包绝对值示例从固定 W=1 的线性网络出发，经过 ReLU 仍失败，再用 ReLU(XW)+ReLU(-XW) 的共享分支结构通过目标。它验证目标绑定、图修订、原型执行、失败记录和留出终止，不是实际论文性能复现或通用架构设计 benchmark。真实训练及更广算子支持仍需另行实现与测量。

