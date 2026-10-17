# v2.1：架构契约与比较证据

此文件用于定义部件、构建数据流、评估替换、解释消融。实际字段定义来自 ontology.json 的 architecture_contract，生成 schema 后由 checker 执行。

## 接口兼容与等价

`swap_assessments` 每项包含 candidate、relation、conditions、evidence_claim_ids。candidate 必须出现在该部件 swap_family 中。

- interface_compatible：声明候选能遵守接口；不说明输出数值、精度或训练行为相同。
- behaviorally_equivalent：在给定输入域、参数对应和条件下行为相同；必须指向该部件的 derivation claim。
- implementation_equivalent：相同数学计算的实现形式；必须指向该部件的 derivation claim，并写数值精度/容限条件。
- unknown：尚未确认；保留为缺口，严格检查/发布会阻塞。

checker 只能验证已登记的接口与证据指针。候选是否真正实现接口、推导是否正确、等价是否成立仍需人工或代码实验验证。f(x)=x 和 g(x)=2x 接口相同而行为不同，不允许据此合并。

## 带类型的数据流

`dataflow.node_parts` 列出本次粒度下的计算节点，其元素引用 parts[].id。
每个 parts 项必须是节点，或在 bindings 中作为 annotation/measurement 绑定到节点。避免为了满足分类清单，虚构“位置形式”“交互范围”“参数量”等独立计算节点。细分激活、归一化等计算时，应将其升为节点并补真实端口；只讨论其所在块的属性时可以绑定，但不能同时两种表示。

每个端口包含：

| 字段 | 语义 |
|---|---|
| id / owner | 全局唯一端口 ID / 所属计算部件 ID |
| direction | input 或 output |
| object_type | tensor、scalar、sequence、field、point_set、state |
| shape | 正整数或非空符号的轴长度，scalar 为 [] |
| axes | 与 shape 同长度的语义轴名称 |
| dtype | 明确数值类型；unknown 会阻塞严格检查 |
| unit | 单位的规范字符串；无量纲用 1 |
| measure | 采样/积分测度约定 |
| state | 状态语义；无状态用 none |
| external | 从图外提供的输入，或交付图外的输出 |

边只允许 output→input。相连端口的 object_type/shape/axes/dtype/unit/measure/state 必须逐项一致。当前采用保守精确比较，不解符号方程、不做单位换算；需要 transpose、cast、lift、插值或单位变换时，明确增加适配节点。

每个内部输入必须有且仅有一个生产者；多来源用独立 merge 节点。内部输出必须有消费者，最终结果标 external=true。普通 data 边 delay=0 且图必须无环；循环状态使用 kind=state、delay>=1 和非 none 的状态语义。延迟单位是本图约定的一步，具体时间单位写入契约条件。

`shared_parameters` 记录 id、parts、description；`coupled_replacements` 记录 id、parts、reason。它们是需要审阅的显式声明，不是从模型代码自动发现的事实。

## 提案的实际影响范围

- affected_parts：实际受影响部件集合，必须包含 targets_part。
- replacement_scope：independent、coupled、rearchitecture 或 unknown。独立替换只允许一个受影响部件；unknown 阻塞严格检查。
- changes_shared_parameters：被修改的共享参数组；必须覆盖其全部使用者。仅使用共享参数而不修改它时允许为空。
- contribution_rationale：为什么目标改动可能改善指定指标；不能仅写“作者说它重要”。

若 affected_parts 与任意联动组相交，必须包含该组全部部件。多个重叠联动组均检查，因而要求覆盖传递影响。

## 重要性证据与消融

每个部件的 importance 分开记录：

- claimed_centrality：作者强调与对应 claim_ids。
- theoretical_dependency：理论结论依赖与对应 claim_ids。
- ablation_ids：消融记录 ID。
- interaction_ids：成对交互记录 ID。

前两项 status 使用 documented/unknown/not_claimed。documented 必须有该部件的证据 claim；记录存在不能证明其推理正确。unknown 是合法研究结论，不要求凑消融。旧 load_bearing 不参与筛选、数量门槛或贡献判断。

每条 ablation 明确：干预部件、共同基线 control_id、指标、干预方式、参数/训练/调参预算及数据拆分是否 matched、是否重训、种子、delta 与置信区间、measurement claim。每个受影响部件必须有直接 measurement 证据。缺少公开数值时不编造 delta/置信区间，不登记虚假数值记录，保留 unknown 并在 gaps 说明。

attribution 仅允许 associational、controlled_comparison、inconclusive。controlled_comparison 要求四类控制均 matched、重训 yes、至少两个种子。满足这些记录条件也不能称为因果效应已被证明，更不能将论文摘要强调直接升级为因果事实。当前不检查种子实验是否真的执行或置信区间计算是否正确。

成对 interaction 要有 A、B、AB 三条消融，指标与 control_id 相同；contrast = delta_AB - delta_A - delta_B。置信区间必须包含 contrast；controlled_comparison 要求三条消融均满足受控记录条件。统计估计方法和不确定度传播仍需研究者说明，checker 只检查关系和算术一致性。

## 版本迁移与验证边界

无版本 v1、2.0.0、2.1.0 与 2.2.0 可用 migrate_anatomy.py 生成当前版本 blocked 草稿。迁移不从 io_in/io_out 散文猜端口，不从 load_bearing 猜作者强调或因果重要性，不编造消融或交互。缺失 dataflow、importance 和提案范围必须补齐后才能 checkpoint。

G1 的累积摘要包含 dataflow、ablations、interactions；更改这些字段会使后续摘要失效。报告将图、重要性、比较条件与提案范围显式投影出来，再保留完整 JSON 快照。

v2.4 增加宿主 AI 引文支撑、数学与行为等价审查、受限精确有理式证明，以及判断驱动的 GitHub 源码检索。参见 semantic-review.md 与 repository-discovery.md。一般数学结论仍属模型辅助审查，实验效果与新研究质量 benchmark 需另行验证。


## 数值判定与证据快照

成本项、预测效果和否定条件使用 `numeric_checks.py` 的受限表达式。变量和结果必须带兼容单位；比较条件记录 metric、工况、聚合、最少种子、运算符和阈值。没有 paired observations 时保持 pending。

publication 断言使用 `evidence_snapshots[]`。`evidence_snapshots.py` 只处理已经保存的原始文件和 UTF-8 提取文件，不负责下载、OCR 或解释 PDF。它重算两个文件哈希并核对 quote 的 Unicode 字符区间。路径必须在 bundle 内。
