# 真实论文与代码架构评测

开发材料包位于工作区 `arch-anatomy-workspace/real-architecture-eval/`，不将完整论文和第三方源码装进技能包。材料固定 arXiv 原文、GitHub commit、来源文件、原始行号、SHA-256 和许可证。案例包括 minGPT、torchvision Bottleneck、neuraloperator SpectralConv 及原始 Transformer 论文，覆盖 code-only、paper-and-code、paper-only。

## 三类证据分别报告

1. 宿主审查 agent 的真实运行：冻结输入、输出原文、技能快照、agent/暴露元数据与修订记录。不同 agent 属于同一模型族；不将上下文隔离称为独立人类验证，也不保证无预训练记忆。
2. 校验器构造变异：对同一产物绕过族分别执行旧/新 validator。这是契约回归，不是 AI 预测，计数不能冒充模型错误放行率。
3. 数值反例：有限前向输入可以反驳“所有输入精确等价”，相同输出不能证明普遍等价；具体运行源码与数学代理必须分开写。

## 标注与评分

参考初稿来自主 agent 的逐源分析，另有独立 agent 参考稿，保留合议、源码行号更正与粒度争议。现在的 reference.json 仍为 human_review_status=pending，不能声称已经是人工标注金标准。

```bash
python scripts/architecture_benchmark.py score --cases CASES.json --reference REFERENCE.json --predictions-dir RUN_DIR -o SCORE.json
python scripts/architecture_benchmark.py annotation-sheet --cases CASES.json --reference REFERENCE.json -o human-review.csv
python scripts/architecture_benchmark.py apply-human --cases CASES.json --reference REFERENCE.json --sheet human-review.csv -o human-reference.json
```

CSV 每行由真实审阅者填写 human_decision=approve/correct/exclude、reviewer 和 rationale；correct 还写 corrected_label。replacement 不允许直接 exclude，困难项应标 unresolved。输入与参考哈希必须一致；空表不会自动批准。此接口只验证显式填写，不能鉴别真实身份。AI 不得替人填写后标为人工认可。更改证据范围、增删条目或粒度要版本化参考 JSON 并重出表，不能暗改评分答案。

评分先验证 case/input_hash、完整题目覆盖、原始证据行号、每段 <=12 行、算子/判断类型与 reference 自身。每个操作预测最多匹配一个参考单元，采用最大二分匹配，避免一条粗粒度“attention”覆盖全部细节。

- 漏检代理 = 未匹配参考单元 / 参考单元数。它依赖类型与证据锚点，分类不同、引用构造而非调用以及粒度不同都可能导致未匹配，必须逐项诊断，不能直接称实际语义漏检率。
- 错误放行 = reference 非 admit、预测 admit 的数量 / reference 非 admit 数。conditional/unresolved 不算直接放行，但其精确分类另计。
- 安全正例召回 = reference admit 且预测 admit / reference admit 数。全拒绝会得到 0，不能用低错误放行掩盖过度拒绝。
- 同时报首轮协议有效率、格式修订次数、所有缺失/失败/未决题；修订不能冒充新的盲测样本。

分开保存 54 个功能检查点与 102 个独立细粒度参考，不把论文 head/layer 模板数与源码逐调用数混合解释。两种口径分数都保留；不能挑高分一套隐藏另一套。unmatched_predictions 可能是正确的更细拆解，不自动算幻觉。

## 已观测到的开发失败与改进

基线与改进在功能检查点、错误放行和安全正例上均饱和，不能声称通用模型能力提升。细粒度未匹配暴露出三类问题：算子分类未统一、构造与调用锚点区别、代数公式内布局操作是否独立列出。后续新评测冻结以下规则：split/concat/view/transpose 属 layout family，contiguous 属 storage/materialization；需要更细的 opcode 时增加 subtype，不用 other 随意代替。显式矩阵转置即使与乘法同一行，也在微操作口径单列；功能口径可组合但必须说明。保留当前 v1 的严格分数，不追溯改标注制造提升。

改进运行曾有一条跨未提供空行的引用；原始输出保留为 round1，修订只接收格式错误，不接收正确答案。独立参考和主参考也出现行号与过长跨度问题，更正记录完整保留。说明参考本身需要复核，不能拿 AI draft 冒充绝对真值。

校验器已修复“所有审查项 not_applicable 仍 admit”的漏洞。interface/function_class 必须 satisfied；其余不适用项须有证据；精确等价 proof 引用全部为 derived。该门仍无法识别一个格式完备但语义错误的推导，语义审查和反例实验不可跳过。

## 下一轮必须增强的设计

本轮题目是开发集，已用于调整指令，不能当 untouched holdout。新增私有或近期陌生架构、动态分支、共享缓存、训练态统计、复数/奇数网格、梯度与分布式状态等留出任务；先冻结重复粒度和参考，再运行至少多个种子/独立上下文或不同模型族。真实人类审阅者确认参考后才能对外报告 human-gold 指标；样本小且同源，不给虚假的置信区间。
