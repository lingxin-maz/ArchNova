---
name: arch-anatomy
description: 面向神经网络论文、源码仓库或两者的底层架构逆向与再设计。恢复计算图、张量接口、状态更新、函数空间、算子和复杂度，按功能沉淀组件素材库，检索可复用部件并设计可证伪的新网络。用户要求读论文架构、分析代码架构、替换算子、部件拆解、架构创新或改造神经网络时使用；支持 paper-only、code-only、paper-and-code。
---

# 架构解剖（Arch Anatomy）

把一篇论文的神经网络架构变成**可替换、可验证、可计量**的部件结构，并在此基础上给出能被证伪的改进方案。

## 输入与组件工作流（优先路由）

核心交付是神经网络计算图、底层算子、可复用组件及新架构设计。先读 `references/input-modes.md`，选择 paper-only / code-only / paper-and-code 并生成宿主任务图；按图完成实际分析，命令本身不执行 AI 判断。拆解与复用时读 `references/component-library.md`，以 `assets/component-schema.json` 保存组件、构建索引和筛选候选。

只有代码时，以代码位置与快照恢复数学描述，保留 theory_status=reconstructed_or_unverified；只有论文时，不声称存在或验证了真实实现。双来源先独立恢复计算图再对齐。深入到公式、状态、参数共享、不变量、离散化、复杂度假设与替换条件。新架构交付统一计算图、实现计划、最小实验、消融及否定标准。

现有 anatomy.json 论文发布门仍要求主论文证据。code-only 及缺少正式证据的任务交付独立 mode-plan、component records、候选和设计文档；不得伪造 paper.source_id 或声称通过研究发布门。参考组件的结构验证与检索命中不证明理论、实现等价或性能提升。

三个核心任务必须阅读 `references/operator-design-review.md`，按 `assets/architecture-task.schema.json` 交付并校验 JSON；通用宿主响应遵循 `assets/host-response.schema.json`。组件规范版本为 1.1，旧组件显式迁移，不静默放行。审查 completed 仅表示审查结束，若 verdict=unresolved/reject，下游只生成修订与验证计划。

运行真实论文/代码质量评测时读取 `references/architecture-benchmark.md`，保存固定来源、原始预测、参考标注版本和暴露情况。AI 标注草稿不能标成人工 gold；漏检、错误放行、安全正例召回及校验器对抗结果分别报告，不以单一分数替代真实能力评估。

## PyTorch/JAX、训练、性能与搜索

需要框架代码、权重训练、GPU 测量或架构搜索时，读取 `references/framework-training-benchmark-search.md`。这些能力通过固定环境、显式 unavailable、受限 IR 和原始收据接入；不支持的任意网络/算子不能伪装成已编译。task_spec 可声明 framework/training/benchmark/search，结果必须保留版本、设备、随机性、预算和回放边界。

## 目标合同、实际原型与实验闭环

要求反向设计并执行时，先读 `references/executable-design-loop.md`。使用 `task_spec.py` 固定外部接口、数据/目标哈希、硬约束和预算；三入口带 --task-spec 后，设计/审查需附受支持 runtime_ir，实际原型和 experiment_loop 追加到 DAG。完整 operators/dataflow/runtime_ir/task_spec_hash 共同绑定，不只比较端口图。

先用 `architecture_ir.make_task_artifact` 导出与执行 IR 一致的声明，再构建 prototype_builder bundle 并提交。没有目标合同的流程只产出 prototype_planner；不支持的算子不冒充已生成原型。实验需真实执行与回放，开发失败可在固定预算内修订；留出失败必须终止，不能再看留出结果继续选候选。具体支持范围和随包可运行示例以 executable-design-loop.md 为准。

## v2.5 执行契约（优先于历史示例）

首次运行、迁移旧产物或发布时，读取 `references/validation-workflow.md`。做模型评测、精确公式检查、行为实验或主动反证检索时，读取 `references/reliability-workflows.md`，按需执行对应段落。定义部件、建图或解释消融时，读取 `references/architecture-contract.md` 和 `validation-workflow.md`。

- 唯一枚举源为 `ontology.json`；`build_ontology.py` 生成 schema、常量和本体说明。checker **实际执行 JSON Schema Draft 4 验证**，依赖 `requirements.txt` 中的 `jsonschema`；依赖缺失即失败。
- 新产物必须声明 `schema_version: "2.5.0"`。`sources[]` 登记来源；`paper.source_id` 指向主论文。部件的 `slot` 使用 R1/M2 等槽位 ID，`claim_ids` 放在部件顶层，`claims[].subject` 必须与引用它的部件 ID 相同。`load_bearing` 旧布尔值不再作为准入条件。
- F 部件必须有指向主论文来源的 direct/paper_fact claim；U/D 必须有相应 upstream_fact/derivation claim。引用存在、引文支持主张、研究结论成立是不同验证层次。checker 重算原始文件与提取文本哈希、逐字核对引文；`semantic_review.py` 准备审查任务，由当前宿主 AI 对照引文上下文判断支撑程度，并检查定理与等价证明的假设、定义域和逐步推理。缺材料或未决项不能判 supported。
- `metrics[].direction` 仅允许 `lower_better/higher_better/neutral`。`cost_model.dominant_part_ids` 必须精确指向成本主项部件。`upstream[].fills_gap` 必须为精确 gap ID 或 M 部件 ID。
- `stage.receipts` 保存 G0–G8 的累积产物摘要；产物变化会使后续摘要失效。它是失效检测，不能证明工作真实发生过。完整草稿填完后用 `checkpoint_anatomy.py` 重新执行本地严格检查并产生摘要；未解决的 blocking_items 不会被自动清除。
- `report.md` 从 JSON 自动生成，禁止独立修改事实。checker 的 `--report` 会核对完整投影，允许 Windows/Linux 换行差异。

从本技能目录执行（文件名按实际产物替换）：

```bash
python -m pip install -r requirements.txt
python scripts/build_ontology.py --check
python scripts/checkpoint_anatomy.py anatomy.draft.json -o anatomy.json
python scripts/render_report.py anatomy.json -o report.md
python scripts/check_anatomy.py anatomy.json --strict --report report.md
python scripts/check_anatomy.py anatomy.json --release --report report.md
python -B -m unittest discover -s tests -v
```

`--release` 要求 v2、G8/passed、无阻塞/告警、报告一致，并联网核验主论文、下游、上游、claim 的 publication 来源及登记引用。合成 fixture 只能通过本地结构回归，**必须被研究发布门拒绝**。网络错误也导致发布失败。发布分为 honest_report 与 supported_conclusions：前者允许明确标记 open、conditional、rejected 和 insufficient 的结果，但不能把它们写成 endorsed；后者要求所有结论 supported。证明依赖必须无环，前提未支持时结论自动降级。一般数学结论仍是模型辅助审查；仅受限有理恒等式有精确机器证明。

旧产物不会静默按当前版本放行：用 `check_anatomy.py old.json --legacy` 只做旧格式结构审阅；用 `migrate_anatomy.py old.json -o draft.v2.json` 将无版本 v1、2.0.0、2.1.0、2.2.0、2.3.0 或 2.4.0 数据转成 blocked 草稿，再人工补端口、证据与比较条件。迁移不会编造 claim、指标、成本主项或通过状态，未补齐的草稿预期校验失败。


## 多模态论文材料

论文包含架构图、流程图、表格或图片公式时，读取 `references/multimodal-workflow.md`，先用 `scripts/multimodal_ingest.py` 登记页面/图像材料，再把 `make_vision_task()` 生成的视觉任务交给多 Agent 调度器。视觉判断必须保留图像 SHA-256、页码和区域；没有图像后端时如实返回 `unavailable`，不能把文本摘要当视觉核验。

## 多 Agent 调度与宿主接管

需要长流程、多个独立判断或跨论文/源码/反证并行时，读取 `references/orchestration.md`，使用 `scripts/orchestrator.py` 管理任务 DAG。调度器把阅读、引文验证、数学审查、GitHub 检索、反证检索和整合拆为带 `task_id`、`input_hash`、角色和依赖的任务；无依赖任务可并行，失败按有界次数重试。宿主 AI 通过 `host-request.json` 接管判断，再用 `submit` 返回；过期、冲突、缺依赖或未完成任务不会被标成完成。调度状态独立保存在运行目录，研究 JSON 只接收经过现有校验器验证的结果。

## 引文、证明、实现与评测的执行方式

默认由正在执行技能的 AI 完成判断，无须另配 API key。脚本提供材料绑定、任务和检查门，不会代替 AI 阅读来源与源码。无人值守时可显式配置兼容 chat-completions 的服务，见语义审查文档。

```bash
python scripts/semantic_review.py prepare anatomy.draft.json -o review-tasks.json
# 宿主 AI 阅读任务与实际材料，写出 reviews.json；不得复制示例判断
python scripts/semantic_review.py apply anatomy.draft.json --reviews reviews.json -o anatomy.reviewed.json
python scripts/checkpoint_anatomy.py anatomy.reviewed.json -o anatomy.json
python scripts/github_repos.py --plan repo-plan.json --anatomy anatomy.draft.json --limit 3 --max-code-files 3 -o repos.json
# 宿主 AI 阅读源码并写 repo-reviews.json
python scripts/github_repos.py --assess repos.json --reviews repo-reviews.json -o repos.assessed.json
```

对每条保留 proposal 运行 repository_coverage，登记 searched/not_found/unavailable/skipped；没有检索记录不能 release。源码候选可沿 import 关系继续追踪。适配后可用 experiment_runner.py 比较输出、状态和梯度，但有限样本通过不等于全域等价。

评测审查质量时使用 review_evaluation.py 的 prepare/collect 或端点 run，必须保存随机任务、分离的答案键、原始响应、模型身份、暴露状态和分母。模拟/无来源 predictions 不显示为模型准确率。

把评审后的仓库结果加入草稿后重新 checkpoint。引文、证明、接口、需求或源码变化时，相应旧判断必须重新审查。检索无结果、限流、网络故障与代码不可读分别记录；不能假装已经找到了实现，也不因搜不到代码而否定一个数学判断。仓库代码默认仅阅读，不自动安装或执行。

## 核心洞察

**架构改进需要定位计算、约束与信息流，提出可检验的替换或拓扑变化。** 所以解剖的目的不是列清单，而是让每个部件满足三条：

1. 有 I/O 契约（写清 `in`/`out` 的语义，不只是形状）
2. 记录交换评估：接口兼容、行为等价、实现等价或未知；需要联动时显式列出受影响部件
3. 有不变式（替换时什么必须保持不变）

未知条件应记录为缺口。接口相同不能证明计算等价，能前向运行也不能证明行为保持。

## 五条铁律

1. **证据可归因**。每个部件、每个数值必须标 `F`（论文事实+位置）/ `U`（上游论文+标识）/ `D`（自己推导+步骤）/ `M`（检索后缺失+检索记录）。没有标记的断言视为无效。
2. **不编造**。标识、数值、结构，任一项不确定就标 `M`。`M` 不是失败，它精确指出论文的可复现性缺口，是高价值信息。
3. **改进必须可证伪**。每个提案要有 `target_metric`、预测量级、破坏什么、`kill_criterion`（否定式、可判定）。写不出 kill criterion 的不是提案，是猜想（放进报告的猜想节）。
4. **类比必须过同构检验**。跨领域借用要有对象映射 φ、被保持的不变式、以及「源方法的保证是否依赖未被保持的性质」的裁决。裁决 reject 的类比放进「已排除」，不允许出现在提案里。
5. **按目标与证据确定靶点**。`importance` 分别记录作者强调、理论依赖、消融与交互；缺证据写 unknown。成本主项可优先研究，稳定性、可辨识性、可靠性等目标也可以构成贡献，但必须写 `contribution_rationale`、指标与否定条件。

## 流水线

九个阶段，每个阶段有**判定门**。门不过就不要进入下一阶段——带病推进会让后面的所有结论失效。

### Stage 0 · 取全文、定靶

- 取全文：arXiv id → `read_arxiv_paper`；DOI → `read_by_doi`；本地 PDF → 用 `pdf` 技能；粘贴文本 → 直接用。
- 只锁定**一个**核心架构：摘要主句点名的 → Fig.1 画出的 → 主结果表用的，按此优先级。多规模变体取支撑主张的那一档，其余只记「改了哪个槽位」。
- 记录：中心主张原句 + 位置、架构图位置、venue/year。
- **门 G0**：能引用中心主张原句，且能指明 Fig.1 或系统图。不能 → 回去补全文，禁止凭标题臆测架构。

### Stage 1 · 契约与部件表

- 先写**接口契约**：输入对象（函数/序列/场/点集）、输出对象、采样测度、断言的对称群。没有契约，部件没有意义。
- 按 `references/part-taxonomy.md` 的十二组（R 输入表示 / P 先验 / B 主干 / M 混合算子 / E 通道 / N 归一化 / G 位置 / O 读出 / L 目标 / T 训练 / I 推理 / S 规模）填表。
- 每行填写 `importance`、`cost_dominant`、`swap_assessments` 与证据；构建 `dataflow` 的节点、端口、连接和属性绑定。
- 写 `granularity_note` 说明为什么停在这个粒度。
- **门 G1**：每行都有 I/O + 不变式 + 证据标记；数据流端口和连接可解析；所有 `M` 项已列清单（Stage 3 要逐项处理）。

### Stage 2 · 成本模型

- 把每类部件的 FLOPs / 状态写出来（公式见 `references/improvement-ops.md` §3.1），合成总成本关于 N（长度/点数）、D（宽度）、P（参数）的表达式。
- 指出**主项阶数**，并判断计算受限还是带宽受限（算术强度）。
- **门 G2**：能在给定规模（如 N=8192, D=4096）下给出主项占总成本的比例。给不出 → 成本模型的假设没写全。

### Stage 3 · 上游补齐

- 对每个 `M`：先判定缺口类型（缺机制/缺数值/缺定义/缺动机），再定向检索——先在该文 `referenced_works` 里找，再 `search_arxiv` 术语原论文。
- 每篇上游必须对应**一个具体槽位与一个具体缺口**。用 `fills_gap` 字段写清。
- **门 G3**：每个 `M` 要么升级为 `U`，要么进入 `gaps` 并写全「查询串 + 端点 + 结果数 + 原因 + 替代思路」。不允许「未找到相关文献」这种无法复核的写法。

### Stage 4 · 下游谱系

- 取引用该文的工作（OpenAlex `cites:` 优先，S2 的 `contexts` 可取引用原句）。
- 每篇写三元组：`addressed_problem`（它认为前作有什么问题）→ `mechanism`（落到具体槽位）→ `new_problem`（它引入的新代价/新失效）。
- **门 G4**：≥3 篇，且至少覆盖**两条不同改进路线**（否则说明只找到一脉）。`new_problem` 一个都不能空。

### Stage 5 · 跨域迁移

- 先写目标问题的数学结构（算子？泛函？约束？），再找结构同源的领域。
- 每个候选按 `references/improvement-ops.md` §7 走四步：φ → 不变式 → 保证依赖检查 → 裁决（admit / weaken / reject）。
- **门 G5**：每个 admit/weaken 都有显式映射表；reject 的进「已排除的类比」并写明哪个不变式没保住。

### Stage 6 · 理论下潜

- 按 `references/theory-descent.md` 走 L1→L4：函数类实例化 → 表达力与速率（**逐条核对定理假设**）→ 算子重构（核/谱/半群显式形式）→ 上一层算子及其成立条件。
- 采用精确检查时，用 formal_statement 显式写变量含义、实数语义、定义域与 lhs/rhs，再用 math_binding.py 绑定实际目标；逐项审查 formalization 义务，禁止拿无关恒等式为目标背书。
- **门 G6**：L2 至少一条结论给出「假设是否满足」的逐条核对；做不到就标 `missing` 并说明缺什么，禁止用「万能逼近」充当解释。

### Stage 7 · 前沿与提案

- 阅读 `references/repository-discovery.md`。每个拟保留的改进判断都要执行“判断 → 机制/需求/接口 → GitHub 查询 → 阅读核心源码 → 适配判断”。从自己的瓶颈分析、算子替换、数值方法、数据结构或跨域类比生成查询；不要求对应某篇论文，可以找到通用库、算法模块、内核和工程组件。论文作者仓库仅作为候选的一种。
- AI 写 `assets/repository-plan.example.json` 格式的 plan，运行 `github_repos.py --plan`，再实际阅读返回的源码、commit 和行号。若只拿到调用、测试或包装代码，用导入路径修订 code_hints 继续定位；没有结果也记录查询和失败原因。逐项给出 reusable/adaptable/not_relevant/uncertain、源码依据、接口差异、改动与最小反证实验，运行 `--assess --reviews` 校验后放进 `repository_discoveries[]`。不得把关键词命中或相同形状当成实现吻合。

- 前沿扫描按**槽位术语**检索（不是按模型名），每篇回答「在哪个槽位更好、代价是什么」。
- 提案必填字段以 ontology 和 schema 为准。在指标、机制、失效边界与最小实验之外，填写 `affected_parts`、`replacement_scope`、`changes_shared_parameters` 和 `contribution_rationale`；联动替换或修改共享参数必须覆盖相关部件。
- 对每个保留提案主动检索失败、局限、复现与相反结果，保存 counterevidence_searches 的原始响应；低相关候选要修订查询，不能当作“没有反证”。逐个审查候选，把有来源的相反/限制引文交给语义审查。
- **门 G7**：每个提案的靶点存在，贡献依据明确且受影响部件覆盖已声明依赖；每个提案有可判定的 `kill_criterion` 与最小实验。达不到的降级进「猜想」。

### Stage 8 · 组装与校验

- 按 `references/report-template.md` 填报告；先写机器可读的 `anatomy.json`，再使用 `scripts/render_report.py` 生成报告（复制 `assets/anatomy.skeleton.json` 填写；完整实填示例见 `assets/anatomy.fixture.json`）。
- 枚举值只有这几组英文，写错会被 checker 直接拦下：`tag` ∈ {F,U,D,M}；`theory[].claim_type` ∈ {theorem,derivation,missing}；`claims[].claim_type` 见 ontology.json；`level` ∈ {perturbation,substitution,rearchitecture}；`verdict` ∈ {admit,weaken,reject}；`group` ∈ {R,P,B,M,E,N,G,O,L,T,I,S}。
- 证据标签要和别的小节对得上，checker 查三处交叉一致：有 `upstream` 却没有一个部件标 `U`；`gaps` 非空却没有任何部件标 `M`；`theory` 里没有 `claim_type: missing` 的条目。三条都按告警放行，但它们正是「证据分级形同虚设」的典型症状，不要留到最后。
- 阅读 `references/semantic-review.md` 并运行 `semantic_review.py prepare`。当前宿主 AI 必须实际比较每个引文与主张、逐步审查每个证明/等价断言，输出带 input_hash 与证据 ID 的判断，再用 `apply` 回填。缺证据、外推、反例或未知条件要缩窄/修正断言或保留阻塞，不能为了通过门而填 supported。可用受限 `proof_checks.py` 辅助查恒等式与精确反例。
- 依次 apply、checkpoint、render、检查，修到通过：
  ```bash
  python scripts/check_anatomy.py anatomy.json --strict --report report.md   # 深度取 anatomy.json.depth
  python scripts/check_anatomy.py anatomy.json --release --report report.md # 最终发布门
  ```
- 任何 endorsed 结论都要有完成的反证检索并处理候选；实验收据必须从 raw_json 重算，不信任 passed 字段。
- **门 G8**：真实研究产物的 `--release --report report.md` 检查器 exit 0。任何 `[ERROR]` 必须修掉，不允许「已知问题但先交付」。

## 深度档位

用户没说就用 `standard`。用户说「快速/只要清单/先看看」→ `lite`；说「深挖/要写论文/要投稿」→ `deep`。

| 档 | 覆盖阶段 | 上游 | 下游 | 跨域 | 提案 | 理论 | 典型耗时 |
|---|---|---|---|---|---|---|---|
| `lite` | 0,1,2,5,7(仅1条) | ≥1 | ≥2 | ≥1 | 1 | L1 | 10–15 min |
| `standard` | 0–8 全 | ≥2 | ≥3 | ≥1 | ≥2 | L1–L3 | 30–60 min |
| `deep` | 0–8 全 | ≥5 | ≥8 | ≥3 | ≥3 | L1–L4 | 90 min+，可并行子代理 |

## 工具与环境

- **文献主路径（可用性以当次探测为准）**：`search_arxiv`、`read_arxiv_paper`、`read_by_doi`、`web_fetch`、`web_search`、`scripts/literature.py`（OpenAlex / S2 / Crossref 封装）。
- **AI4Scholar 系工具（`search_papers`/`search_semantic`/`search_pubmed` 等）本机未配置 API key，调用会直接报错**。不要把它们写进主路径。若一次 `get_ai4scholar_credits` 成功，说明已配置，可作为加速层叠加；否则一律走上面的免费组合。
- 详细配方、配额、429 退避、失败记录格式见 `references/retrieval-ladder.md`。
- 本地 PDF：交给 `pdf` 技能抽文本，再按 Stage 0 处理。

## 文件

```
arch-anatomy/
├── SKILL.md                      ← 本文件：流程与铁律
├── references/
│   ├── part-taxonomy.md          ← 12 组槽位定义、swap 测试、终止规则
│   ├── retrieval-ladder.md       ← 免费 API 配方、上游/下游/前沿检索策略
│   ├── improvement-ops.md        ← 三级改动、提案字段契约、四个目标池、算子替换目录
│   ├── theory-descent.md         ← L1–L4、算子重构锚点、伪理论五形态
│   └── report-template.md        ← 固定报告结构
├── scripts/
│   ├── check_anatomy.py          ← 确定性校验（必跑）
│   ├── literature.py             ← OpenAlex/S2/Crossref 查询封装
│   ├── validation_core.py        ← schema、关系和摘要校验
│   ├── migrate_anatomy.py        ← v1 转 blocked v2 草稿
│   ├── checkpoint_anatomy.py     ← 本地校验与摘要生成
│   ├── render_report.py          ← JSON 报告投影
│   └── build_package.py          ← 可复现打包与哈希清单
└── assets/
    ├── anatomy.skeleton.json     ← 空骨架，复制后填写
    └── anatomy.fixture.json      ← 已填满的合成样例（checker 回归基准）
```

单次解剖的产物放在**用户指定的目录**，默认 `./anatomy-<架构名>/`：`report.md` + `anatomy.json` + `evidence/`（存关键引文片段与 API 返回）。

## 写完之前逐条自检

8. 证明依赖是否无环，前提状态是否传递到结论？
9. 每个保留提案是否有实现探索状态和当前目标绑定？
10. 行为等价是否明确区分输出、状态、训练/推理和浮点容差？
11. 有限实验通过是否被误写成普遍证明？
12. 评测是否报告完整分母和合理弃权？

1. 是否把相同 I/O 错判为相同计算？交换评估是否区分兼容与等价，联动约束是否进入数据流？
2. 每个 `M` 都有检索记录吗？`M` 占比超过 30% 时，报告可信度必须降级。
3. 有没有哪个提案的 `breaks` 是空的？（空 → 说明没想清后果，或改动太小不值得提）
4. 下游的 `new_problem` 是不是都在描述「性能差一点」？（是 → 没抓住结构代价）
5. 理论节的引理假设逐条核对过吗？有没有把万能逼近当解释？
6. 报告里的每个标识（arXiv/DOI）都通过了 `--verify-refs` 吗？
7. 如果把这份报告给原作者看，哪一条最可能被反驳？——把它写进「最大不确定性」。

## 常见失败模式

| 症状 | 病因 | 修法 |
|---|---|---|
| 部件表很长但都是常识部件 | 用通用模板套，没读细节 | 回到 Fig.1 与公式，只有原文出现的东西才写 `F` |
| 改进建议像综述摘要 | 没锁 `target_metric`，也没锁部件 | 强制提案字段契约，先写 kill_criterion 再写方案 |
| 下游全是同一路线 | 只按被引排序取前几名 | 按改进路线分组取样，强制覆盖两条路线 |
| 理论节堆术语 | 没有可计算的量 | 要求给出速率/常数/条件数之一的具体形式，否则标 `missing` |
| 跨领域类比牵强 | 跳过了不变式检查 | 走四步检验，reject 的移出提案 |
| 报告 1500 字就结束 | 跳过了下游与理论 | 长度是副产物；检查器会报组覆盖率不足 |
| checker 报 `claim_type 必须是 theorem/derivation/missing` | 把枚举值写成了中文或自造词 | 所有枚举字段（`claim_type`/`level`/`verdict`/`tag`）必须用检查器接受的英文值；写完 `anatomy.json` **立刻**跑一次 checker，不要等报告写完才发现 |
| 提案靶点缺少依据 | 把作者强调、理论依赖和消融观察混为一谈 | 分项记录 importance；按可测目标补 contribution_rationale，证据不足可保持 unknown |

通用神经网络系统本体与实时论文观察见 references/neural-system-ontology.md；使用 network_system.py 生成 LLM、CNN、RNN、状态空间、扩散、GNN、神经算子、多模态和混合系统 profile，使用 research_watch.py 获取带响应哈希和时间收据的最新候选论文。

前沿未实现能力必须先走 references/frontier-capability-design.md 与 frontier_capability_design.py，输出创新假设、接口合同、失败条件、证据要求和验证门，不得用可执行原型的局部支持冒充完整能力。

突破性架构探索入口为 breakthrough_explorer.py；它生成结构新颖候选和机制验证门，不把启发式分数当作突破证明。

网络架构设计协议见 references/architecture-design.md；architecture_design.py 负责架构选择、形状/感受野/序列/注意力/跳连合同和标准交付物。

模型画像、训练策略探索和微观设计见 references/model-diagnostics.md；model_diagnostics.py 会把结构观察、IR 推导和设计提案分开输出。
