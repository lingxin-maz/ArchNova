# -*- coding: utf-8 -*-
"""GENERATED FILE - do not edit.

Source : ontology.json (version 2.5.0)
Rebuild: python scripts/build_ontology.py
"""

ONTOLOGY_VERSION = '2.5.0'

GROUP_ORDER = ['R', 'P', 'B', 'M', 'E', 'N', 'G', 'O', 'L', 'T', 'I', 'S']

GROUPS = {'B': '主干与组合',
 'E': '通道变换',
 'G': '位置与序',
 'I': '推理路径',
 'L': '目标函数',
 'M': '混合算子',
 'N': '归一化与数值',
 'O': '读出与解码',
 'P': '先验载体',
 'R': '输入与表示',
 'S': '规模计量',
 'T': '训练与优化'}

SLOTS = {'B1': '块拓扑',
 'B2': '深度宽度调度',
 'B3': '跨块信息流',
 'B4': '递归与状态机制',
 'B5': '并行结构',
 'E1': '逐点变换',
 'E2': '扩张比与瓶颈',
 'E3': '激活函数',
 'E4': '乘性调制',
 'G1': '编码形式',
 'G2': '基函数',
 'G3': '外推机制',
 'G4': '非序列位置的定位',
 'I1': '单次与自回归',
 'I2': '测试时计算',
 'I3': '近似',
 'I4': '单位成本',
 'L1': '主损失',
 'L2': '辅助与正则',
 'L3': '物理与一致性',
 'L4': '权重平衡',
 'L5': '采样与课程',
 'L6': '保真度结构',
 'M1': '交互范围',
 'M2': '打分-聚合形式',
 'M3': '路由与选择',
 'M4': '多头与分组',
 'M5': '条件化路径',
 'M6': '状态更新规则',
 'N1': '归一化类型与轴',
 'N2': '位置',
 'N3': '仿射与条件化',
 'N4': '数值稳定',
 'O1': '聚合读出',
 'O2': '解码方式',
 'O3': '输出参数化',
 'O4': '约束投影',
 'P1': '局部性',
 'P2': '对称群',
 'P3': '关系结构',
 'P4': '多尺度',
 'P5': '几何与流形',
 'P6': '因果性',
 'R1': '离散化单元',
 'R2': '提升算子',
 'R3': '连续坐标编码',
 'R4': '输入标度',
 'R5': '条件注入点',
 'R6': '掩码与分组',
 'S1': '参数分解',
 'S2': 'FLOPs 分解',
 'S3': '状态与显存',
 'S4': '通信与带宽',
 'T1': '优化器与调度',
 'T2': '精度与并行',
 'T3': '初始化与稳定性',
 'T4': '有效 batch 与序列长度'}

SLOT_GROUP = {'B1': 'B',
 'B2': 'B',
 'B3': 'B',
 'B4': 'B',
 'B5': 'B',
 'E1': 'E',
 'E2': 'E',
 'E3': 'E',
 'E4': 'E',
 'G1': 'G',
 'G2': 'G',
 'G3': 'G',
 'G4': 'G',
 'I1': 'I',
 'I2': 'I',
 'I3': 'I',
 'I4': 'I',
 'L1': 'L',
 'L2': 'L',
 'L3': 'L',
 'L4': 'L',
 'L5': 'L',
 'L6': 'L',
 'M1': 'M',
 'M2': 'M',
 'M3': 'M',
 'M4': 'M',
 'M5': 'M',
 'M6': 'M',
 'N1': 'N',
 'N2': 'N',
 'N3': 'N',
 'N4': 'N',
 'O1': 'O',
 'O2': 'O',
 'O3': 'O',
 'O4': 'O',
 'P1': 'P',
 'P2': 'P',
 'P3': 'P',
 'P4': 'P',
 'P5': 'P',
 'P6': 'P',
 'R1': 'R',
 'R2': 'R',
 'R3': 'R',
 'R4': 'R',
 'R5': 'R',
 'R6': 'R',
 'S1': 'S',
 'S2': 'S',
 'S3': 'S',
 'S4': 'S',
 'T1': 'T',
 'T2': 'T',
 'T3': 'T',
 'T4': 'T'}

GROUP_SLOTS = {'B': ['B1', 'B2', 'B3', 'B4', 'B5'],
 'E': ['E1', 'E2', 'E3', 'E4'],
 'G': ['G1', 'G2', 'G3', 'G4'],
 'I': ['I1', 'I2', 'I3', 'I4'],
 'L': ['L1', 'L2', 'L3', 'L4', 'L5', 'L6'],
 'M': ['M1', 'M2', 'M3', 'M4', 'M5', 'M6'],
 'N': ['N1', 'N2', 'N3', 'N4'],
 'O': ['O1', 'O2', 'O3', 'O4'],
 'P': ['P1', 'P2', 'P3', 'P4', 'P5', 'P6'],
 'R': ['R1', 'R2', 'R3', 'R4', 'R5', 'R6'],
 'S': ['S1', 'S2', 'S3', 'S4'],
 'T': ['T1', 'T2', 'T3', 'T4']}

LAYERS = {'$comment': '架构部件与实验配置必须分层，避免把训练技巧和硬件优化当成架构改进',
 'architecture': ['R', 'P', 'B', 'M', 'E', 'N', 'G', 'O'],
 'inference': ['I'],
 'measurement': ['S'],
 'training': ['L', 'T']}

PROPOSAL_FIELDS = ['target_metric',
 'targets_part',
 'level',
 'mechanism',
 'predicted_effect',
 'breaks',
 'repair',
 'min_experiment',
 'kill_criterion',
 'affected_parts',
 'replacement_scope',
 'changes_shared_parameters',
 'contribution_rationale',
 'id',
 'numerical_prediction',
 'decision_rule']

PROPOSAL_ARITY_NOTE = '提案必填字段以本表和生成 schema 为准；不再使用固定元组数量的称呼。'

TAGS = ['D', 'F', 'M', 'U']

TAG_INFO = {'D': {'means': '从公式或复杂度模型推导得出', 'name': 'derivation', 'needs': ['derivation']},
 'F': {'means': '本体论文直接陈述或给出的式子', 'name': 'paper_fact', 'needs': ['claim_ids']},
 'M': {'means': '论文与上游都没有，已记录检索失败', 'name': 'missing', 'needs': ['search_record']},
 'U': {'means': '本体没写，由上游文献补齐', 'name': 'upstream_fact', 'needs': ['claim_ids']}}

CLAIM_TYPES = ['paper_fact', 'upstream_fact', 'derivation', 'measurement', 'assumption']

SUPPORT_TYPES = ['direct', 'indirect', 'contradicted']

CLAIM_FIELDS = ['claim_id', 'subject', 'predicate', 'object', 'claim_type', 'evidence']

EVIDENCE_ITEM_FIELDS = ['source_id', 'locator', 'quote', 'retrieved_at', 'content_hash', 'support']

LEVELS = ['perturbation', 'substitution', 'rearchitecture']

VERDICTS = ['admit', 'weaken', 'reject']

THEORY_CLAIM_TYPES = ['theorem', 'derivation', 'missing']

STAGE_STATUS = ['pending', 'in_progress', 'passed', 'blocked', 'downgraded']

ASSUMPTION_STATUS = ['satisfied', 'violated', 'uncertain', 'missing']

STAGES = [{'artifact': 'paper + core_architecture',
  'id': 'G0',
  'invariant': 'claim_quote 有 F 证据且指到具体位置',
  'name': '取全文定靶'},
 {'artifact': 'interface_contract + parts + typed dataflow + importance',
  'id': 'G1',
  'invariant': '部件接口、连接和属性绑定可解析；兼容与行为等价分开记录',
  'name': '契约与部件表'},
 {'artifact': 'cost_model',
  'id': 'G2',
  'invariant': 'dominant_term 落在某个 cost_dominant 部件上',
  'name': '成本模型'},
 {'artifact': 'upstream + U 类 claim',
  'id': 'G3',
  'invariant': '每个缺口都能指到 fills_gap',
  'name': '上游补齐'},
 {'artifact': 'downstream + claims', 'id': 'G4', 'invariant': '至少两条不同改进路线', 'name': '下游谱系'},
 {'artifact': 'cross_domain',
  'id': 'G5',
  'invariant': '每条有 correspondence/preserved_invariant/verdict',
  'name': '跨域迁移'},
 {'artifact': 'theory + theorem records',
  'id': 'G6',
  'invariant': '假设逐条标注 satisfied/violated/uncertain',
  'name': '理论下潜'},
 {'artifact': 'proposals',
  'id': 'G7',
  'invariant': '提案字段完整，affected_parts 覆盖联动和被修改共享参数的使用者，贡献依据明确',
  'name': '前沿与提案'},
 {'artifact': 'report',
  'id': 'G8',
  'invariant': 'release 模式下 errors=0 且无 blocking warning',
  'name': '组装与校验'}]

DEPTH_LIMITS = {'deep': {'claims': 40,
          'downstream': 8,
          'groups': 10,
          'parts': 12,
          'proposals': 3,
          'upstream': 5},
 'lite': {'claims': 8, 'downstream': 2, 'groups': 6, 'parts': 8, 'proposals': 1, 'upstream': 1},
 'standard': {'claims': 20,
              'downstream': 3,
              'groups': 8,
              'parts': 8,
              'proposals': 2,
              'upstream': 2}}

CROSS_CHECKS = {'X1': {'rule': 'proposal.targets_part 必须存在，affected_parts 覆盖联动关系，贡献依据必须写明；载荷/成本不是唯一准入条件',
        'severity': 'error'},
 'X10': {'rule': 'gaps 非空却没有任何部件标 M', 'severity': 'warning'},
 'X11': {'rule': 'theory 里没有 claim_type=missing 的条目', 'severity': 'warning'},
 'X12': {'rule': 'downstream 的 mechanism 两两雷同（视为伪路线多样性）', 'severity': 'error'},
 'X13': {'rule': '发布必须 G8/passed，无阻塞；前序 receipts 必须匹配累积产物摘要', 'severity': 'error'},
 'X14': {'rule': 'claim evidence.source_id 必须登记在 sources，F 必须引用 paper.source_id',
         'severity': 'error'},
 'X15': {'rule': 'claim.subject 必须精确等于引用它的部件 id', 'severity': 'error'},
 'X16': {'rule': 'v2 必须声明 schema_version 并实际通过 JSON Schema 验证', 'severity': 'error'},
 'X17': {'rule': '接口兼容不蕴含行为等价；等价主张必须有同部件 derivation claim，仍需人工审查', 'severity': 'error'},
 'X18': {'rule': '数据流端口方向、对象、形状、轴、dtype、单位、测度和状态必须兼容；状态反馈显式延迟', 'severity': 'error'},
 'X19': {'rule': '摘要强调、定理依赖、消融和交互分别记录；受控比较必须满足预算、数据、重训及多种子条件', 'severity': 'error'},
 'X2': {'rule': 'proposal.target_metric 必须出现在 metrics 或 cost_model 的指标名中', 'severity': 'error'},
 'X20': {'rule': 'publication 证据发布时必须绑定本地原始/提取快照，重算哈希并精确核对 Unicode 引文区间', 'severity': 'error'},
 'X21': {'rule': '成本与预测表达式必须有界执行且单位匹配；否定条件在没有观测时保持 pending', 'severity': 'error'},
 'X22': {'rule': '标题弱匹配或同名候选不自动选择，保留 ambiguous 与查询响应快照', 'severity': 'error'},
 'X23': {'rule': 'Semantic reviews bind actual and transitive proof material; release '
                 'dispositions cannot endorse unresolved or negative conclusions.',
         'severity': 'error'},
 'X24': {'rule': 'Exact real-scalar rational checks propagate every undefined-domain guard, '
                 'including zero powers; non-real semantics remain inconclusive.',
         'severity': 'error'},
 'X25': {'rule': 'GitHub 搜索由提案机制和接口需求驱动；匹配论文或关键词不等于官方或可复现', 'severity': 'error'},
 'X26': {'rule': 'Proof dependencies must be acyclic; conclusions inherit unresolved or '
                 'negative premise status.',
         'severity': 'error'},
 'X27': {'rule': 'Each retained proposal accounts for implementation exploration with current '
                 'target binding and actual search receipts or explicit skipped reason.',
         'severity': 'release error'},
 'X28': {'rule': 'Execution receipts bind declared adapter files, cases, observables and '
                 'current target; passing finite comparisons do not establish universal '
                 'equivalence.',
         'severity': 'error'},
 'X29': {'rule': 'Exact machine equations must bind the actual natural/formal target, scalar '
                 'symbols, operator AST and domain; semantic formalization remains a separate '
                 'review obligation.',
         'severity': 'error'},
 'X3': {'rule': 'proposal.predicted_effect 必须引用某个 metrics[].id 或 cost_model 项',
        'severity': 'warning'},
 'X30': {'rule': 'Saved experiment outcomes are recomputed from hash-verified raw responses '
                 'and complete case/repetition observations; passing flags are not trusted.',
         'severity': 'error'},
 'X31': {'rule': 'Retained proposals and endorsed claims require active counter-search '
                 'receipts; endorsements must resolve candidate assessments grounded in '
                 'original-source snapshots.',
         'severity': 'release error'},
 'X32': {'rule': 'Evaluation evidence distinguishes simulated/unverified predictions from '
                 'recorded model runs, exposes prior exposure and binds opaque tasks, prompts '
                 'and raw response objects.',
         'severity': 'error'},
 'X4': {'rule': 'upstream[].fills_gap 必须精确指向 gaps[].id 或某个标 M 的部件', 'severity': 'error'},
 'X5': {'rule': 'theory[].source 必须指向已登记的 claim_id 或可解析的 arXiv/DOI', 'severity': 'warning'},
 'X6': {'rule': 'parts[].claim_ids 必须都能在 claims[] 里找到', 'severity': 'error'},
 'X7': {'rule': '标 F 的部件至少要有一条 support=direct 的 paper_fact claim', 'severity': 'error'},
 'X8': {'rule': 'cost_model.dominant_part_ids 必须精确指向 cost_dominant=true 的部件',
        'severity': 'error'},
 'X9': {'rule': '有 upstream 却没有部件标 U', 'severity': 'warning'}}

RELEASE_POLICY = {'$comment': '发布模式默认把 blocking severity 一律当失败，避免 errors=0 但内容空洞仍然 exit 0',
 'fail_on_any_warning': True,
 'fail_on_error': True,
 'fail_on_unverified_refs': True,
 'fail_on_warning': ['X3', 'X5', 'X9', 'X10', 'X11'],
 'missing_ratio_action': 'downgrade',
 'missing_ratio_limit': 0.3}

