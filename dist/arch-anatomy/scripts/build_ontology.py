#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate every derived artifact from ontology.json.

Single source of truth:  <skill>/ontology.json
Derived (all overwritten on each run, never edit by hand):

    <skill>/assets/anatomy.schema.json   JSON Schema for anatomy.json v2
    <skill>/scripts/ontology_gen.py      constants imported by check_anatomy.py
    <skill>/references/ontology.md       human-readable tables used by SKILL.md

Usage:
    python scripts/build_ontology.py            # regenerate
    python scripts/build_ontology.py --check    # exit 1 if anything is stale

Python 3.7 compatible, standard library only.
"""
from __future__ import annotations

import io
import json
import os
import pprint
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ONTOLOGY = os.path.join(ROOT, "ontology.json")

SCHEMA_OUT = os.path.join(ROOT, "assets", "anatomy.schema.json")
PY_OUT = os.path.join(HERE, "ontology_gen.py")
MD_OUT = os.path.join(ROOT, "references", "ontology.md")

BANNER_PY = '''# -*- coding: utf-8 -*-
"""GENERATED FILE - do not edit.

Source : ontology.json (version {version})
Rebuild: python scripts/build_ontology.py
"""

ONTOLOGY_VERSION = {version!r}

'''


def load_ontology():
    with io.open(ONTOLOGY, encoding="utf-8-sig") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# ontology_gen.py
# ---------------------------------------------------------------------------
def gen_python(o):
    groups = {}
    slots = {}
    slot_group = {}
    group_slots = {}
    for g in o["groups"]:
        groups[g["id"]] = g["name"]
        ids = []
        for s in g["slots"]:
            slots[s["id"]] = s["name"]
            slot_group[s["id"]] = g["id"]
            ids.append(s["id"])
        group_slots[g["id"]] = ids

    ev = o["evidence"]
    depth = {}
    for name, lim in o["depth_limits"].items():
        depth[name] = dict(lim)
    cross = {c["id"]: {"rule": c["rule"], "severity": c["severity"]}
             for c in o["cross_checks"]}

    out = [BANNER_PY.format(version=o["version"])]
    for name, value in [
        ("GROUP_ORDER", [g["id"] for g in o["groups"]]),
        ("GROUPS", groups),
        ("SLOTS", slots),
        ("SLOT_GROUP", slot_group),
        ("GROUP_SLOTS", group_slots),
        ("LAYERS", o["layers"]),
        ("PROPOSAL_FIELDS", [f["name"] for f in o["proposal_fields"]]),
        ("PROPOSAL_ARITY_NOTE", o["proposal_arity_note"]),
        ("TAGS", sorted(ev["tags"].keys())),
        ("TAG_INFO", ev["tags"]),
        ("CLAIM_TYPES", list(ev["claim_types"])),
        ("SUPPORT_TYPES", list(ev["support_types"])),
        ("CLAIM_FIELDS", list(ev["claim_fields"])),
        ("EVIDENCE_ITEM_FIELDS", list(ev["evidence_item_fields"])),
        ("LEVELS", list(o["enums"]["level"])),
        ("VERDICTS", list(o["enums"]["verdict"])),
        ("THEORY_CLAIM_TYPES", list(o["enums"]["claim_type"])),
        ("STAGE_STATUS", list(o["enums"]["stage_status"])),
        ("ASSUMPTION_STATUS", list(o["enums"]["assumption_status"])),
        ("STAGES", o["stages"]),
        ("DEPTH_LIMITS", depth),
        ("CROSS_CHECKS", cross),
        ("RELEASE_POLICY", o["release_policy"]),
    ]:
        out.append("%s = %s\n\n" % (
            name, pprint.pformat(value, width=96)))
    return "".join(out)


# ---------------------------------------------------------------------------
# assets/anatomy.schema.json
# ---------------------------------------------------------------------------
def gen_schema(o):
    ev = o["evidence"]
    tag_branches = []
    for tag in sorted(ev["tags"]):
        needs = ev["tags"][tag]["needs"]
        tag_branches.append({
            "properties": {
                "tag": {"enum": [tag]},
                "claim_ids": {"type": "array", "items": {"type": "string"}},
                "derivation": {"type": "string", "minLength": 20},
                "search_record": {
                    "type": "object",
                    "required": ["queries", "endpoints", "reason"],
                    "properties": {
                        "queries": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                        "endpoints": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                        "reason": {"type": "string", "minLength": 4},
                    },
                },
            },
            "required": ["tag"] + [n for n in needs if n != "claim_ids"],
        })

    claim_evidence = {
        "type": "array",
        "minItems": 1,
        "items": {
            "type": "object",
            "required": ["source_id", "locator", "support"],
            "properties": {
                "source_id": {"type": "string", "minLength": 3},
                "locator": {"type": "string", "minLength": 1},
                "quote": {"type": "string"},
                "retrieved_at": {"type": "string"},
                "content_hash": {"type": "string"},
                "support": {"enum": list(ev["support_types"])},
            },
        },
    }

    part = {
        "type": "object",
        "required": ["id", "group", "slot", "name", "io_in", "io_out",
                     "invariant", "swap_family", "load_bearing",
                     "cost_dominant", "evidence", "claim_ids"],
        "properties": {
            "id": {"type": "string", "minLength": 2},
            "group": {"enum": [g["id"] for g in o["groups"]]},
            "slot": {"enum": sorted({s["id"] for g in o["groups"] for s in g["slots"]})},
            "name": {"type": "string", "minLength": 1},
            "io_in": {"type": "string", "minLength": 1},
            "io_out": {"type": "string", "minLength": 1},
            "invariant": {"type": "string", "minLength": 1},
            "swap_family": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "load_bearing": {"type": "boolean", "description": "Ignored legacy display field; no causal inference or proposal gate"},
            "cost_dominant": {"type": "boolean"},
            "layer": {"enum": list(o["layers"].keys())},
            "claim_ids": {"type": "array", "items": {"type": "string"}},
            "evidence": {"oneOf": tag_branches},
            "granularity_note": {"type": "string"},
        },
    }

    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "$comment": "GENERATED from ontology.json v%s by scripts/build_ontology.py" % o["version"],
        "title": "arch-anatomy anatomy.json v2",
        "type": "object",
        "required": ["schema_version", "sources", "paper", "core_architecture", "interface_contract", "parts",
                     "claims", "metrics", "cost_model", "upstream", "downstream",
                     "cross_domain", "proposals", "theory", "gaps", "stage"],
        "definitions": {
            "part": part,
            "claim": {
                "type": "object",
                "required": ["claim_id", "subject", "predicate", "object", "claim_type", "evidence"],
                "properties": {
                    "claim_id": {"type": "string", "pattern": "^claim:"},
                    "subject": {"type": "string"},
                    "predicate": {"type": "string"},
                    "object": {"type": "string"},
                    "claim_type": {"enum": list(ev["claim_types"])},
                    "evidence": claim_evidence,
                    "note": {"type": "string"},
                },
            },
            "metric": {
                "type": "object",
                "required": ["id", "name", "direction"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "definition": {"type": "string"},
                    "unit": {"type": "string"},
                    "direction": {"enum": ["lower_better", "higher_better", "neutral"]},
                },
            },
            "proposal": {
                "type": "object",
                "required": [f["name"] for f in o["proposal_fields"]],
                "properties": {
                    "target_metric": {"type": "string"},
                    "targets_part": {"type": "string"},
                    "level": {"enum": list(o["enums"]["level"])},
                    "mechanism": {"type": "string"},
                    "predicted_effect": {"type": "string"},
                    "breaks": {"type": "string"},
                    "repair": {"type": "string"},
                    "min_experiment": {"type": "string"},
                    "kill_criterion": {"type": "string"},
                    "refs": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "properties": {
            "schema_version": {"enum": [o["version"]]},
            "sources": {"type": "array", "minItems": 1, "items": {
                "type": "object", "required": ["id", "kind", "title"],
                "properties": {"id": {"type": "string", "minLength": 1},
                    "kind": {"enum": ["publication", "synthetic", "local"]},
                    "title": {"type": "string", "minLength": 1},
                    "ref": {"type": "string", "minLength": 1}}}},
            "paper": {
                "type": "object",
                "required": ["title", "ids", "source_id"],
                "properties": {
                    "title": {"type": "string", "minLength": 1},
                    "ids": {"type": "object"},
                    "source_id": {"type": "string", "minLength": 1},
                    "venue_year": {"type": "string"},
                },
            },
            "core_architecture": {"type": "object"},
            "interface_contract": {"type": "object"},
            "parts": {"type": "array", "minItems": 4, "items": {"$ref": "#/definitions/part"}},
            "claims": {"type": "array", "minItems": 1, "items": {"$ref": "#/definitions/claim"}},
            "metrics": {"type": "array", "minItems": 1, "items": {"$ref": "#/definitions/metric"}},
            "cost_model": {"type": "object", "required": ["dominant_part_ids"],
                "properties": {"dominant_part_ids": {"type": "array", "minItems": 1,
                    "uniqueItems": True, "items": {"type": "string"}}}},
            "upstream": {"type": "array", "items": {"type": "object",
                "required": ["fills_gap"], "properties": {"fills_gap": {"type": "string"}}}},
            "downstream": {"type": "array", "items": {"type": "object"}},
            "cross_domain": {"type": "array", "items": {"type": "object"}},
            "proposals": {"type": "array", "items": {"$ref": "#/definitions/proposal"}},
            "theory": {"type": "array", "items": {"type": "object"}},
            "gaps": {"type": "array", "items": {"type": "object",
                "required": ["id"], "properties": {"id": {"type": "string", "minLength": 1}}}},
            "stage": {
                "type": "object",
                "required": ["stage", "stage_status", "blocking_items", "receipts"],
                "properties": {
                    "stage": {"enum": [s["id"] for s in o["stages"]]},
                    "stage_status": {"enum": list(o["enums"]["stage_status"])},
                    "blocking_items": {"type": "array", "items": {"type": "string"}},
                    "receipts": {"type": "array", "items": {"type": "object",
                        "required": ["stage", "status", "digest"],
                        "properties": {"stage": {"enum": [s["id"] for s in o["stages"]]},
                            "status": {"enum": ["passed"]}, "digest": {"type": "string",
                                "pattern": "^[a-f0-9]{64}$"}}}},
                },
            },
            "depth": {"enum": list(o["depth_limits"].keys())},
        },
    }
    contract = o['architecture_contract']
    schema['definitions'].update(contract['definitions'])
    schema['definitions']['part']['required'].remove('load_bearing')
    schema['definitions']['part']['required'].extend(contract['part_properties'])
    schema['definitions']['part']['properties'].update(contract['part_properties'])
    schema['definitions']['proposal']['properties'].update(contract['proposal_properties'])
    schema['properties'].update(contract['top_properties'])
    schema['required'].extend(contract['top_properties'])
    verification = o['verification_contract']
    schema['definitions'].update(verification['definitions'])
    schema['properties'].update(verification['top_properties'])
    schema['required'].extend(verification['top_properties'])
    schema['definitions']['claim']['properties']['evidence']['items']['properties'].update(verification['evidence_properties'])
    schema['definitions']['proposal']['properties'].update(verification['proposal_properties'])
    schema['properties']['cost_model']['required'].append('calculation')
    schema['properties']['cost_model']['properties']['calculation'] = {'$ref': '#/definitions/calculation'}
    schema['definitions']['metric']['required'].extend(['unit', 'definition'])
    reviews = o['review_contract']
    schema['definitions'].update(reviews['definitions'])
    schema['properties'].update(reviews['top_properties'])
    schema['required'].extend(reviews['top_properties'])
    schema['definitions']['claim']['properties']['proof_outline'] = {'$ref':'#/definitions/proof_outline'}
    schema['definitions']['claim']['properties']['formal_statement']={'$ref':'#/definitions/formal_statement'}
    swap=schema['definitions']['swap_assessment']
    swap['required'].append('id')
    swap['properties']['id']={'type':'string','minLength':1}
    swap['properties']['formal_statement']={'$ref':'#/definitions/formal_statement'}
    swap['properties']['proof_outline']={'$ref':'#/definitions/proof_outline'}
    swap['properties']['comparison_contract']={'$ref':'#/definitions/comparison_contract'}
    schema['properties']['theory']['items']={'type':'object','required':['id'],
        'properties':{'id':{'type':'string','minLength':1},'proof_outline':{'$ref':'#/definitions/proof_outline'},'formal_statement':{'$ref':'#/definitions/formal_statement'}}}
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# references/ontology.md
# ---------------------------------------------------------------------------
def gen_markdown(o):
    L = []
    A = L.append
    A("# 本体（Ontology）")
    A("")
    A("> **生成文件，勿手改。** 源文件是 `ontology.json` v%s；改完源文件跑 "
      "`python scripts/build_ontology.py`，本文件与 `assets/anatomy.schema.json`、"
      "`scripts/ontology_gen.py` 会一起重写。" % o["version"])
    A("")
    A("这份表的唯一职责：让模型、用户、校验器对「合法结构」有同一份定义。"
      "字段名与槽位号在任何别的文档里出现时，都以此处为准。")
    A("")

    A("## 1. 十二组与槽位")
    A("")
    A("| 组 | 名称 | 这一组在问什么 | 槽位 |")
    A("|---|---|---|---|")
    for g in o["groups"]:
        ids = " ".join(s["id"] for s in g["slots"])
        A("| %s | %s | %s | %s |" % (g["id"], g["name"], g["question"], ids))
    A("")
    for g in o["groups"]:
        A("### %s. %s（%s）" % (g["id"], g["name"], g["id"]))
        A("")
        A("| 槽位 | 名称 | 这一槽在问什么 |")
        A("|---|---|---|")
        for s in g["slots"]:
            A("| %s | %s | %s |" % (s["id"], s["name"], s["question"]))
        A("")

    A("## 2. 分层：架构 / 训练 / 推理 / 计量")
    A("")
    A("替换一个**架构**部件，不能被训练技巧或硬件优化混进来。每个部件用 `layer` 声明自己属于哪层，"
      "提案的 `targets_part` 指向 training 或 inference 层时，必须说明它为何是架构问题。")
    A("")
    A("| 层 | 组 |")
    A("|---|---|")
    for name, gids in o["layers"].items():
        if name.startswith("$"):
            continue
        A("| %s | %s |" % (name, ", ".join(gids)))
    A("")

    A("## 3. 提案字段（%d 项）" % len(o["proposal_fields"]))
    A("")
    A(o["proposal_arity_note"])
    A("")
    A("| 字段 | 含义 |")
    A("|---|---|")
    for f in o["proposal_fields"]:
        extra = (" 枚举：`%s`" % "|".join(o["enums"][f["enum"]])) if "enum" in f else ""
        A("| `%s` | %s%s |" % (f["name"], f.get("means", "见枚举"), extra))
    A("")

    A("## 4. 证据类型")
    A("")
    A("标签只是指针；真正的证据在 `claims[]` 里，每条 claim 带一组 `evidence[]`（含 locator、quote、"
      "retrieved_at、content_hash、support）。")
    A("")
    A("| 标签 | 名称 | 必须带 | 含义 |")
    A("|---|---|---|---|")
    for tag in sorted(o["evidence"]["tags"]):
        info = o["evidence"]["tags"][tag]
        A("| %s | %s | %s | %s |" % (tag, info["name"],
                                     ", ".join("`%s`" % n for n in info["needs"]),
                                     info["means"]))
    A("")
    A("- claim_type：" + "、".join("`%s`" % c for c in o["evidence"]["claim_types"]))
    A("- support：" + "、".join("`%s`" % c for c in o["evidence"]["support_types"]))
    A("")

    A("## 5. 枚举")
    A("")
    A("| 字段 | 合法值 |")
    A("|---|---|")
    for name in ["level", "verdict", "claim_type", "stage_status", "assumption_status"]:
        A("| `%s` | %s |" % (name, " | ".join("`%s`" % v for v in o["enums"][name])))
    A("")

    A("## 6. 交叉关系校验")
    A("")
    A("校验器不只查字段非空，还查这些关系。`--release` 下 error 与 blocking warning 都算失败。")
    A("")
    A("| 编号 | 规则 | 级别 |")
    A("|---|---|---|")
    for c in o["cross_checks"]:
        A("| %s | %s | %s |" % (c["id"], c["rule"], c["severity"]))
    A("")

    A("## 7. 深度档位")
    A("")
    A("| 档位 | " + " | ".join(sorted(next(iter(o["depth_limits"].values())).keys())) + " |")
    A("|---" * (len(next(iter(o["depth_limits"].values()))) + 1) + "|")
    keys = sorted(next(iter(o["depth_limits"].values())).keys())
    for name in ["lite", "standard", "deep"]:
        lim = o["depth_limits"][name]
        A("| %s | %s |" % (name, " | ".join(str(lim[k]) for k in keys)))
    A("")

    A("## 8. 阶段与门")
    A("")
    A("| 阶段 | 名称 | 产物 | 不变量 |")
    A("|---|---|---|---|")
    for s in o["stages"]:
        A("| %s | %s | %s | %s |" % (s["id"], s["name"], s["artifact"], s["invariant"]))
    A("")
    A("产物里的 `stage` 对象必须如实填写：")
    A("")
    A("```json")
    A('"stage": {"stage": "G4", "stage_status": "blocked",'
      ' "blocking_items": ["下游只找到一条路线"]}')
    A("```")
    A("")
    A("`stage_status` 取 " + "、".join("`%s`" % v for v in o["enums"]["stage_status"]) +
      "。`blocked` 时必须写 `blocking_items`，且 release 模式判失败。")
    A("")

    A("## 9. 命名变更表（旧写法已废弃）")
    A("")
    A("| 旧 | 新 | 说明 |")
    A("|---|---|---|")
    for row in [
        ("节字母前缀 F1–F4", "N1–N4", "归一化与数值组，机器字段一直是 N"),
        ("节字母前缀 H1–H4", "O1–O4", "读出与解码组，机器字段一直是 O"),
        ("节字母前缀 I1–I6", "L1–L6", "目标函数组，机器字段一直是 L"),
        ("节字母前缀 J1–J4", "T1–T4", "训练与优化组，机器字段一直是 T"),
        ("节字母前缀 K1–K4", "I1–I4", "推理路径组，机器字段一直是 I"),
        ("节字母前缀 L1–L4", "S1–S4", "规模计量组，机器字段一直是 S"),
        ("七元组/九元组", "提案字段契约", "字段随版本演化，数量与必填项以当前 ontology/schema 为准"),
    ]:
        A("| %s | %s | %s |" % row)
    A("")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    check_only = "--check" in argv
    o = load_ontology()
    outputs = [
        (SCHEMA_OUT, gen_schema(o)),
        (PY_OUT, gen_python(o)),
        (MD_OUT, gen_markdown(o)),
    ]
    stale = []
    for path, text in outputs:
        data = text.encode("utf-8")
        old = None
        if os.path.exists(path):
            with open(path, "rb") as fh:
                old = fh.read()
        if old == data:
            continue
        stale.append(os.path.relpath(path, ROOT))
        if not check_only:
            directory = os.path.dirname(path)
            if directory and not os.path.isdir(directory):
                os.makedirs(directory)
            with open(path, "wb") as fh:
                fh.write(data)
    if check_only:
        if stale:
            print("[STALE] %s" % ", ".join(stale))
            print("run: python scripts/build_ontology.py")
            return 1
        print("[OK] generated artifacts match ontology.json")
        return 0
    if stale:
        print("[WROTE] %s" % ", ".join(stale))
    else:
        print("[OK] nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main())
