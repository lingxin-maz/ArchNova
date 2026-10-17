# 本体（Ontology）

> **生成文件，勿手改。** 源文件是 `ontology.json` v2.5.0；改完源文件跑 `python scripts/build_ontology.py`，本文件与 `assets/anatomy.schema.json`、`scripts/ontology_gen.py` 会一起重写。

这份表的唯一职责：让模型、用户、校验器对「合法结构」有同一份定义。字段名与槽位号在任何别的文档里出现时，都以此处为准。

## 1. 十二组与槽位

| 组 | 名称 | 这一组在问什么 | 槽位 |
|---|---|---|---|
| R | 输入与表示 | 网络看到的最小单元是什么，什么信息在这一步被销毁 | R1 R2 R3 R4 R5 R6 |
| P | 先验载体 | 哪些结构是硬约束，哪些只是软偏好 | P1 P2 P3 P4 P5 P6 |
| B | 主干与组合 | 深度方向如何串联，状态如何跨步传递 | B1 B2 B3 B4 B5 |
| M | 混合算子 | 信息在位置之间如何交换（含 attention 与一切替代品） | M1 M2 M3 M4 M5 M6 |
| E | 通道变换 | 每个位置上特征如何被重写 | E1 E2 E3 E4 |
| N | 归一化与数值 | 统计量沿哪些轴取，数值如何不炸 | N1 N2 N3 N4 |
| G | 位置与序 | 顺序信息如何编码，能否外推 | G1 G2 G3 G4 |
| O | 读出与解码 | 输出如何被聚合与生成 | O1 O2 O3 O4 |
| L | 目标函数 | 每一项在拉扯什么 | L1 L2 L3 L4 L5 L6 |
| T | 训练与优化 | 常被省略但决定架构可行性 | T1 T2 T3 T4 |
| I | 推理路径 | 部署时的行为可能与训练时不同 | I1 I2 I3 I4 |
| S | 规模计量 | 派生层：这一层不是抄来的，是算出来的 | S1 S2 S3 S4 |

### R. 输入与表示（R）

| 槽位 | 名称 | 这一槽在问什么 |
|---|---|---|
| R1 | 离散化单元 | token / patch / node / collocation point / 像素 |
| R2 | 提升算子 | 离散单元到 d 维向量怎么做的 |
| R3 | 连续坐标编码 | 连续坐标如何进入网络 |
| R4 | 输入标度 | 是否逐通道或逐域归一化 |
| R5 | 条件注入点 | 保真度、边界条件、物性参数从哪一层进 |
| R6 | 掩码与分组 | padding / sensor / 分组结构如何影响聚合 |

### P. 先验载体（P）

| 槽位 | 名称 | 这一槽在问什么 |
|---|---|---|
| P1 | 局部性 | 感受野由什么界定 |
| P2 | 对称群 | 断言了哪个群的等变或不变性 |
| P3 | 关系结构 | 图、拉普拉斯、注意力掩码、边界算子 |
| P4 | 多尺度 | 是否分层、金字塔、小波、多重网格 |
| P5 | 几何与流形 | 数据在网格、流形、点云还是规则域 |
| P6 | 因果性 | 是否强制单向依赖 |

### B. 主干与组合（B）

| 槽位 | 名称 | 这一槽在问什么 |
|---|---|---|
| B1 | 块拓扑 | 残差或稠密或并行分支，norm 在支路内外 |
| B2 | 深度宽度调度 | 各层宽度、是否跨层共享权重 |
| B3 | 跨块信息流 | skip、门控、早退、超连接 |
| B4 | 递归与状态机制 | 有没有显式状态：RNN hidden、KV cache、SSM state、memory token |
| B5 | 并行结构 | 序列化 scan、块并行、树形归约 |

### M. 混合算子（M）

| 槽位 | 名称 | 这一槽在问什么 |
|---|---|---|
| M1 | 交互范围 | 全对全 / 局部 / 稀疏 / 全局 token |
| M2 | 打分-聚合形式 | 具体代数形式 |
| M3 | 路由与选择 | top-k、MoE、硬注意力、检索 |
| M4 | 多头与分组 | 头数、共享方式、头间交互 |
| M5 | 条件化路径 | 除了自混合，还混合什么 |
| M6 | 状态更新规则 | 对 SSM/线性注意力：A,B,C,Delta 如何离散化 |

### E. 通道变换（E）

| 槽位 | 名称 | 这一槽在问什么 |
|---|---|---|
| E1 | 逐点变换 | MLP、单线性、门控 MLP |
| E2 | 扩张比与瓶颈 | FFN 扩张比、低秩分解 |
| E3 | 激活函数 | 形式与其光滑性/频谱性质 |
| E4 | 乘性调制 | FiLM、scale-shift、门控 |

### N. 归一化与数值（N）

| 槽位 | 名称 | 这一槽在问什么 |
|---|---|---|
| N1 | 归一化类型与轴 | LayerNorm/RMSNorm/BatchNorm/GroupNorm 沿哪些轴求统计量 |
| N2 | 位置 | pre/post/sandwich、QK-norm 与残差支路的相对位置 |
| N3 | 仿射与条件化 | 是否可学习 gamma/beta，是否由输入产生 |
| N4 | 数值稳定 | eps、fp32 upcast、logit cap、残差缩放、初始化缩放 |

### G. 位置与序（G）

| 槽位 | 名称 | 这一槽在问什么 |
|---|---|---|
| G1 | 编码形式 | 绝对/相对/旋转/学习/无 |
| G2 | 基函数 | 正弦、Fourier、随机特征 |
| G3 | 外推机制 | NTK-aware、ALiBi、长度课程 |
| G4 | 非序列位置的定位 | 网格索引、坐标、拓扑序 |

### O. 读出与解码（O）

| 槽位 | 名称 | 这一槽在问什么 |
|---|---|---|
| O1 | 聚合读出 | CLS/均值/末位/注意力池化/算子基系数 |
| O2 | 解码方式 | 自回归/并行/扩散/流匹配/直接回归 |
| O3 | 输出参数化 | logits、均值方差、分布、场值、基系数 |
| O4 | 约束投影 | 对称性、守恒、边界条件的硬编码 |

### L. 目标函数（L）

| 槽位 | 名称 | 这一槽在问什么 |
|---|---|---|
| L1 | 主损失 | 函数形式与定义域 |
| L2 | 辅助与正则 | 负载均衡、熵、平滑、谱正则 |
| L3 | 物理与一致性 | PDE 残差、守恒、无散度 |
| L4 | 权重平衡 | 固定 lambda、不确定性加权、GradNorm、自适应 |
| L5 | 采样与课程 | 配点分布、LHS、重要性采样、数据混比 |
| L6 | 保真度结构 | 多保真如何组合 |

### T. 训练与优化（T）

| 槽位 | 名称 | 这一槽在问什么 |
|---|---|---|
| T1 | 优化器与调度 | Adam/AdamW/SGD，warmup，衰减步长 |
| T2 | 精度与并行 | bf16/fp8、TP/PP/EP、切分方式 |
| T3 | 初始化与稳定性 | 初始化缩放、梯度裁剪 |
| T4 | 有效 batch 与序列长度 | 与架构设计强耦合的实验条件 |

### I. 推理路径（I）

| 槽位 | 名称 | 这一槽在问什么 |
|---|---|---|
| I1 | 单次与自回归 | 缓存策略，是否维护跨步状态 |
| I2 | 测试时计算 | 采样、CoT、搜索、迭代精化 |
| I3 | 近似 | 量化、稀疏、蒸馏、剪枝 |
| I4 | 单位成本 | 每 token 或每 query 的 FLOPs、字节、延迟 |

### S. 规模计量（S）

| 槽位 | 名称 | 这一槽在问什么 |
|---|---|---|
| S1 | 参数分解 | 每个部件的参数量，谁占主导 |
| S2 | FLOPs 分解 | 写成 N、D、P 的函数，标出主项阶数 |
| S3 | 状态与显存 | KV cache / SSM state / 激活值 |
| S4 | 通信与带宽 | 并行下的 collective 量级 |

## 2. 分层：架构 / 训练 / 推理 / 计量

替换一个**架构**部件，不能被训练技巧或硬件优化混进来。每个部件用 `layer` 声明自己属于哪层，提案的 `targets_part` 指向 training 或 inference 层时，必须说明它为何是架构问题。

| 层 | 组 |
|---|---|
| architecture | R, P, B, M, E, N, G, O |
| training | L, T |
| inference | I |
| measurement | S |

## 3. 提案字段（16 项）

提案必填字段以本表和生成 schema 为准；不再使用固定元组数量的称呼。

| 字段 | 含义 |
|---|---|
| `target_metric` | 优化哪个指标，必须能在 metrics 里找到 |
| `targets_part` | 打哪个部件，必须存在；按贡献依据与可测目标选择，不能仅凭载荷布尔值准入 |
| `level` | 见枚举 枚举：`perturbation|substitution|rearchitecture` |
| `mechanism` | 改动如何改变数据流或复杂度 |
| `predicted_effect` | 预测的效果，必须引用 metrics 里的定义或 cost_model 的项 |
| `breaks` | 这个改动会破坏什么 |
| `repair` | 破坏如何补救 |
| `min_experiment` | 最小可证伪实验 |
| `kill_criterion` | 什么结果算否证，必须含判定词与阈值 |
| `affected_parts` | 实际受影响的部件 ID，含所有联动与被修改共享参数的使用者 |
| `replacement_scope` | 独立替换、联动替换或重构 |
| `changes_shared_parameters` | 本提案修改的共享参数组 ID |
| `contribution_rationale` | 目标部件与可测目标之间的诊断依据；无需先有载荷布尔结论 |
| `id` | 全局唯一提案 ID |
| `numerical_prediction` | 可执行资源预测；单位与数值必须匹配成本模型 |
| `decision_rule` | 否定条件的结构化表达；指标、工况、种子、聚合和阈值明确 |

## 4. 证据类型

标签只是指针；真正的证据在 `claims[]` 里，每条 claim 带一组 `evidence[]`（含 locator、quote、retrieved_at、content_hash、support）。

| 标签 | 名称 | 必须带 | 含义 |
|---|---|---|---|
| D | derivation | `derivation` | 从公式或复杂度模型推导得出 |
| F | paper_fact | `claim_ids` | 本体论文直接陈述或给出的式子 |
| M | missing | `search_record` | 论文与上游都没有，已记录检索失败 |
| U | upstream_fact | `claim_ids` | 本体没写，由上游文献补齐 |

- claim_type：`paper_fact`、`upstream_fact`、`derivation`、`measurement`、`assumption`
- support：`direct`、`indirect`、`contradicted`

## 5. 枚举

| 字段 | 合法值 |
|---|---|
| `level` | `perturbation` | `substitution` | `rearchitecture` |
| `verdict` | `admit` | `weaken` | `reject` |
| `claim_type` | `theorem` | `derivation` | `missing` |
| `stage_status` | `pending` | `in_progress` | `passed` | `blocked` | `downgraded` |
| `assumption_status` | `satisfied` | `violated` | `uncertain` | `missing` |

## 6. 交叉关系校验

校验器不只查字段非空，还查这些关系。`--release` 下 error 与 blocking warning 都算失败。

| 编号 | 规则 | 级别 |
|---|---|---|
| X1 | proposal.targets_part 必须存在，affected_parts 覆盖联动关系，贡献依据必须写明；载荷/成本不是唯一准入条件 | error |
| X2 | proposal.target_metric 必须出现在 metrics 或 cost_model 的指标名中 | error |
| X3 | proposal.predicted_effect 必须引用某个 metrics[].id 或 cost_model 项 | warning |
| X4 | upstream[].fills_gap 必须精确指向 gaps[].id 或某个标 M 的部件 | error |
| X5 | theory[].source 必须指向已登记的 claim_id 或可解析的 arXiv/DOI | warning |
| X6 | parts[].claim_ids 必须都能在 claims[] 里找到 | error |
| X7 | 标 F 的部件至少要有一条 support=direct 的 paper_fact claim | error |
| X8 | cost_model.dominant_part_ids 必须精确指向 cost_dominant=true 的部件 | error |
| X9 | 有 upstream 却没有部件标 U | warning |
| X10 | gaps 非空却没有任何部件标 M | warning |
| X11 | theory 里没有 claim_type=missing 的条目 | warning |
| X12 | downstream 的 mechanism 两两雷同（视为伪路线多样性） | error |
| X13 | 发布必须 G8/passed，无阻塞；前序 receipts 必须匹配累积产物摘要 | error |
| X14 | claim evidence.source_id 必须登记在 sources，F 必须引用 paper.source_id | error |
| X15 | claim.subject 必须精确等于引用它的部件 id | error |
| X16 | v2 必须声明 schema_version 并实际通过 JSON Schema 验证 | error |
| X17 | 接口兼容不蕴含行为等价；等价主张必须有同部件 derivation claim，仍需人工审查 | error |
| X18 | 数据流端口方向、对象、形状、轴、dtype、单位、测度和状态必须兼容；状态反馈显式延迟 | error |
| X19 | 摘要强调、定理依赖、消融和交互分别记录；受控比较必须满足预算、数据、重训及多种子条件 | error |
| X20 | publication 证据发布时必须绑定本地原始/提取快照，重算哈希并精确核对 Unicode 引文区间 | error |
| X21 | 成本与预测表达式必须有界执行且单位匹配；否定条件在没有观测时保持 pending | error |
| X22 | 标题弱匹配或同名候选不自动选择，保留 ambiguous 与查询响应快照 | error |
| X23 | Semantic reviews bind actual and transitive proof material; release dispositions cannot endorse unresolved or negative conclusions. | error |
| X24 | Exact real-scalar rational checks propagate every undefined-domain guard, including zero powers; non-real semantics remain inconclusive. | error |
| X25 | GitHub 搜索由提案机制和接口需求驱动；匹配论文或关键词不等于官方或可复现 | error |
| X26 | Proof dependencies must be acyclic; conclusions inherit unresolved or negative premise status. | error |
| X27 | Each retained proposal accounts for implementation exploration with current target binding and actual search receipts or explicit skipped reason. | release error |
| X28 | Execution receipts bind declared adapter files, cases, observables and current target; passing finite comparisons do not establish universal equivalence. | error |
| X29 | Exact machine equations must bind the actual natural/formal target, scalar symbols, operator AST and domain; semantic formalization remains a separate review obligation. | error |
| X30 | Saved experiment outcomes are recomputed from hash-verified raw responses and complete case/repetition observations; passing flags are not trusted. | error |
| X31 | Retained proposals and endorsed claims require active counter-search receipts; endorsements must resolve candidate assessments grounded in original-source snapshots. | release error |
| X32 | Evaluation evidence distinguishes simulated/unverified predictions from recorded model runs, exposes prior exposure and binds opaque tasks, prompts and raw response objects. | error |

## 7. 深度档位

| 档位 | claims | downstream | groups | parts | proposals | upstream |
|---|---|---|---|---|---|---|
| lite | 8 | 2 | 6 | 8 | 1 | 1 |
| standard | 20 | 3 | 8 | 8 | 2 | 2 |
| deep | 40 | 8 | 10 | 12 | 3 | 5 |

## 8. 阶段与门

| 阶段 | 名称 | 产物 | 不变量 |
|---|---|---|---|
| G0 | 取全文定靶 | paper + core_architecture | claim_quote 有 F 证据且指到具体位置 |
| G1 | 契约与部件表 | interface_contract + parts + typed dataflow + importance | 部件接口、连接和属性绑定可解析；兼容与行为等价分开记录 |
| G2 | 成本模型 | cost_model | dominant_term 落在某个 cost_dominant 部件上 |
| G3 | 上游补齐 | upstream + U 类 claim | 每个缺口都能指到 fills_gap |
| G4 | 下游谱系 | downstream + claims | 至少两条不同改进路线 |
| G5 | 跨域迁移 | cross_domain | 每条有 correspondence/preserved_invariant/verdict |
| G6 | 理论下潜 | theory + theorem records | 假设逐条标注 satisfied/violated/uncertain |
| G7 | 前沿与提案 | proposals | 提案字段完整，affected_parts 覆盖联动和被修改共享参数的使用者，贡献依据明确 |
| G8 | 组装与校验 | report | release 模式下 errors=0 且无 blocking warning |

产物里的 `stage` 对象必须如实填写：

```json
"stage": {"stage": "G4", "stage_status": "blocked", "blocking_items": ["下游只找到一条路线"]}
```

`stage_status` 取 `pending`、`in_progress`、`passed`、`blocked`、`downgraded`。`blocked` 时必须写 `blocking_items`，且 release 模式判失败。

## 9. 命名变更表（旧写法已废弃）

| 旧 | 新 | 说明 |
|---|---|---|
| 节字母前缀 F1–F4 | N1–N4 | 归一化与数值组，机器字段一直是 N |
| 节字母前缀 H1–H4 | O1–O4 | 读出与解码组，机器字段一直是 O |
| 节字母前缀 I1–I6 | L1–L6 | 目标函数组，机器字段一直是 L |
| 节字母前缀 J1–J4 | T1–T4 | 训练与优化组，机器字段一直是 T |
| 节字母前缀 K1–K4 | I1–I4 | 推理路径组，机器字段一直是 I |
| 节字母前缀 L1–L4 | S1–S4 | 规模计量组，机器字段一直是 S |
| 七元组/九元组 | 提案字段契约 | 字段随版本演化，数量与必填项以当前 ontology/schema 为准 |

