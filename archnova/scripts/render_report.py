# -*- coding: utf-8 -*-
"""Deterministic projection of anatomy.json. Prose never overrides the source data."""
import argparse
import json
from pathlib import Path


def cell(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str('' if value is None else value).replace('|', '\\|').replace('\r', '').replace('\n', '<br>')


def table(rows, keys):
    out = ['| ' + ' | '.join(keys) + ' |', '| ' + ' | '.join('---' for _ in keys) + ' |']
    for row in rows:
        out.append('| ' + ' | '.join(cell(row.get(key)) for key in keys) + ' |')
    return '\n'.join(out) + '\n'


def render(data):
    paper = data.get('paper', {})
    core = data.get('core_architecture', {})
    out = ['# 架构解剖报告：' + cell(core.get('name')), '',
           '**论文**：' + cell(paper.get('title')), '',
           '引文支撑与一般数学/等价结论由 AI 辅助审查，需查看逐项判断与适用范围；结构通过不证明研究结论。合成来源只用于回归测试。', '',
           '## 0 一页结论', '',
           table([core], ['name', 'claim_quote', 'evidence']),
           table([data.get('stage', {})], ['stage', 'stage_status', 'blocking_items']),
           '## 1 架构提取与部件化', '',
           table([data.get('interface_contract', {})], ['input_object', 'output_object', 'sampling_measure', 'symmetry_asserted']),
           table(data.get('parts', []), ['id', 'group', 'slot', 'name', 'io_in', 'io_out', 'invariant', 'swap_family', 'importance', 'swap_assessments', 'cost_dominant', 'claim_ids', 'evidence', 'granularity_note']),
           '### 带类型的数据流', '',
           table(data.get('dataflow', {}).get('ports', []), ['id','owner','direction','object_type','shape','axes','dtype','unit','measure','state','external']),
           table(data.get('dataflow', {}).get('edges', []), ['id','source','target','kind','delay']),
           table(data.get('dataflow', {}).get('bindings', []), ['part_id','node_parts','role']),
           table(data.get('dataflow', {}).get('shared_parameters', []), ['id','parts','description']),
           table(data.get('dataflow', {}).get('coupled_replacements', []), ['id','parts','reason']),
           '### 消融与交互记录', '',
           '这些是有来源的比较记录；预算匹配和重训检查不等于因果效应已被识别。', '',
           table(data.get('ablations', []), ['id','part_ids','control_id','metric_id','intervention','controls','retraining','seeds','effect','attribution','evidence_claim_ids']),
           table(data.get('interactions', []), ['id','part_ids','metric_id','ablation_ids','contrast','confidence_interval','attribution']),
           '### 成本模型【推断】', '',
           table([data.get('cost_model', {})], ['flops_per_unit', 'dominant_term', 'dominant_part_ids', 'params_breakdown', 'state_bytes_per_unit', 'arithmetic_intensity_note']),
           '## 2 上游补齐', '',
           table(data.get('upstream', []), ['id', 'title', 'fills_gap', 'verified']),
           '## 3 下游分析', '',
           table(data.get('downstream', []), ['id', 'title', 'addressed_problem', 'mechanism', 'new_problem']),
           '## 4 跨领域迁移', '',
           table(data.get('cross_domain', []), ['source_field', 'problem', 'correspondence', 'preserved_invariant', 'verdict', 'reject_reason', 'borrowable']),
           '## 5 理论下潜', '',
           table(data.get('theory', []), ['layer', 'claim_type', 'statement', 'conditions', 'source']),
           '## 6 前沿与改进方案', '',
           table(data.get('metrics', []), ['id', 'name', 'definition', 'direction', 'unit']),
           table(data.get('proposals', []), ['target_metric', 'targets_part', 'affected_parts', 'replacement_scope', 'changes_shared_parameters', 'contribution_rationale', 'level', 'mechanism', 'predicted_effect', 'breaks', 'repair', 'min_experiment', 'kill_criterion', 'refs']),
           '## 7 缺失、可信度与复核', '',
           table(data.get('gaps', []), ['id', 'item', 'queries', 'endpoints', 'reason', 'alternative']),
           '### 来源登记', '',
           table(data.get('sources', []), ['id', 'kind', 'title', 'ref']),
           '### 断言与证据', '',
           table(data.get('claims', []), ['claim_id', 'subject', 'predicate', 'object', 'claim_type', 'evidence']),
           '### 引文支撑与证明审查（模型辅助）', '',
           table(data.get('semantic_reviews', []), ['kind','target_id','verdict','rationale','obligations','evidence_ids','counterexample','scope_limits','reviewer','input_hash']),
           '### 发布模式与结论 disposition', '',
           table([data.get('publication', {})], ['mode','conclusions']),
           '### 提案实现探索覆盖', '',
           table(data.get('repository_explorations', []), ['proposal_id','status','reason','discovery_plan_hashes','target_snapshot_hash']),
           '### 有限适配实验', '',
           table(data.get('implementation_experiments', []), ['target_id','receipt_path','sha256']),
           '### 主动反证检索与原始材料判断', '',
           table(data.get('counterevidence_searches', []), ['id','plan','status','candidates','review','input_hash']),
           '### 精确有理式检查的输入', '',
           table(data.get('mathematical_checks', []), ['id','target_id','case','binding']),
           '### 根据架构判断检索的代码实现', '',
           table(data.get('repository_discoveries', []), ['status','plan','review_status','candidates','errors']),
           '### 完整数据快照', '']
    snapshot = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)
    # Longer fence than any input run prevents an input string closing the snapshot.
    import re
    fence = '`' * max(3, 1 + max([len(m) for m in re.findall(r'`+', snapshot)] or [0]))
    out.extend([fence + 'json', snapshot, fence, ''])
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('anatomy')
    ap.add_argument('-o', '--output')
    args = ap.parse_args(argv)
    data = json.loads(Path(args.anatomy).read_text(encoding='utf-8-sig'))
    from check_anatomy import Report
    from validation_core import schema_check
    rep = Report()
    if not schema_check(data, rep):
        print('\n'.join(rep.errors))
        return 1
    target = Path(args.output) if args.output else Path(args.anatomy).with_name('report.md')
    target.write_text(render(data), encoding='utf-8')
    print(str(target))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
