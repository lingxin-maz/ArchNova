#!/usr/bin/env python3
"""Deterministic validator for an archnova result.

Usage
-----
    python check_anatomy.py anatomy.json
    python check_anatomy.py anatomy.json --report report.md
    python check_anatomy.py anatomy.json --verify-refs
    python check_anatomy.py anatomy.json --strict --json

Exit codes: 0 = pass (warnings allowed), 1 = errors, 2 = bad invocation.

Requires Python 3.7+ and jsonschema (see requirements.txt).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from semantic_review import check_reviews
from evidence_snapshots import check_snapshots
from numeric_checks import check_numeric
from architecture_checks import check_architecture
from validation_core import schema_check, check_graph, check_receipts, canonical_ref

def _force_utf8():
    """Windows consoles default to cp936/GBK; force UTF-8 so Chinese survives."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001  (py<3.7 or redirected to a non-file)
            pass


def _read_text_any(path):
    """Read text tolerating UTF-8 / UTF-8-BOM / GBK, which Windows editors mix up."""
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# Every constant below comes from ontology.json, via the generated module.
# Do not hand-edit: run `python scripts/build_ontology.py` instead.
# ---------------------------------------------------------------------------
try:
    from ontology_gen import (  # noqa: F401
        GROUP_ORDER, GROUPS, SLOTS, SLOT_GROUP, GROUP_SLOTS, LAYERS,
        PROPOSAL_FIELDS, PROPOSAL_ARITY_NOTE, TAGS, TAG_INFO, CLAIM_TYPES,
        SUPPORT_TYPES, LEVELS, VERDICTS, THEORY_CLAIM_TYPES, STAGE_STATUS,
        ASSUMPTION_STATUS, STAGES, DEPTH_LIMITS, CROSS_CHECKS, RELEASE_POLICY,
        ONTOLOGY_VERSION,
    )
except ImportError:  # script invoked from an unexpected cwd
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ontology_gen import (  # noqa: F401
        GROUP_ORDER, GROUPS, SLOTS, SLOT_GROUP, GROUP_SLOTS, LAYERS,
        PROPOSAL_FIELDS, PROPOSAL_ARITY_NOTE, TAGS, TAG_INFO, CLAIM_TYPES,
        SUPPORT_TYPES, LEVELS, VERDICTS, THEORY_CLAIM_TYPES, STAGE_STATUS,
        ASSUMPTION_STATUS, STAGES, DEPTH_LIMITS, CROSS_CHECKS, RELEASE_POLICY,
        ONTOLOGY_VERSION,
    )

TAGS = set(TAGS)
VERDICTS = set(VERDICTS)
LEVELS = set(LEVELS)
# ontology_gen.CLAIM_TYPES is the *evidence* claim vocabulary; the theory section
# uses a different enum. Keep both, under distinct names.
EVIDENCE_CLAIM_TYPES = set(CLAIM_TYPES)
CLAIM_TYPES = set(THEORY_CLAIM_TYPES)
SUPPORT_TYPES = set(SUPPORT_TYPES)
STAGE_STATUS = set(STAGE_STATUS)
ASSUMPTION_STATUS = set(ASSUMPTION_STATUS)
LIMITS = dict(DEPTH_LIMITS["standard"])
SLOT_BY_NAME = dict((v, k) for k, v in SLOTS.items())
SLOT_IDS = set(SLOTS)


REPORT_SECTIONS = [
    ("## 0", "一页结论"),
    ("## 1", "架构提取与部件化"),
    ("## 2", "上游补齐"),
    ("## 3", "下游分析"),
    ("## 4", "跨领域迁移"),
    ("## 5", "理论下潜"),
    ("## 6", "前沿与改进方案"),
    ("## 7", "缺失、可信度与复核"),
]

ARXIV_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
OALEX_RE = re.compile(r"^(https?://openalex\.org/)?W\d+$")


class Report(object):
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.notes = []

    def err(self, path, msg):
        self.errors.append("[ERROR] %s: %s" % (path, msg))

    def warn(self, path, msg):
        self.warnings.append("[WARN]  %s: %s" % (path, msg))

    def note(self, path, msg=None):
        # called as note(msg) for plain notes, note(path, msg) from verify_refs
        if msg is None:
            self.notes.append("[OK]    %s" % path)
        else:
            self.notes.append("[OK]    %s: %s" % (path, msg))


def _nonempty(v):
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, dict, tuple)):
        return len(v) > 0
    return True


def _dict(d, key):
    v = d.get(key)
    return v if isinstance(v, dict) else {}


def _list(d, key):
    v = d.get(key)
    return v if isinstance(v, list) else []


# --------------------------------------------------------------------------
# schema checks
# --------------------------------------------------------------------------

def check_paper(data, rep):
    paper = _dict(data, "paper")
    if not _nonempty(paper.get("title")):
        rep.err("paper.title", "缺失")
    ids = _dict(paper, "ids")
    if not any(_nonempty(ids.get(k)) for k in ("arxiv", "doi", "openalex")):
        rep.err("paper.ids", "arxiv / doi / openalex 至少填一个，否则引用无法核查")
    else:
        rep.note("paper.ids 存在")


def check_core(data, rep):
    core = _dict(data, "core_architecture")
    if not _nonempty(core.get("name")):
        rep.err("core_architecture.name", "缺失（Stage 0 必须锁定单一核心架构）")
    if not _nonempty(core.get("claim_quote")):
        rep.err("core_architecture.claim_quote", "缺失（必须引述论文中心主张原句）")
    ev = _dict(core, "evidence")
    if ev.get("tag") != "F":
        rep.err("core_architecture.evidence.tag", "中心主张必须是论文事实 F")
    elif not _nonempty(ev.get("loc")):
        rep.err("core_architecture.evidence.loc", "F 类证据必须给位置（p7 §3.2 / eq(4) / Tab.2）")


def check_contract(data, rep):
    ct = _dict(data, "interface_contract")
    for k in ("input_object", "output_object", "sampling_measure", "symmetry_asserted"):
        if not _nonempty(ct.get(k)):
            rep.err("interface_contract.%s" % k, "缺失（没有契约，部件没有意义）")


def check_evidence(ev, path, rep, allow_empty=False):
    if not isinstance(ev, dict) or not ev:
        if not allow_empty:
            rep.err(path, "缺少 evidence 对象")
        return None
    tag = ev.get("tag")
    if tag not in TAGS:
        rep.err(path + ".tag", "必须是 F/U/D/M 之一，实际为 %r" % (tag,))
        return None
    if tag == "F" and not _nonempty(ev.get("loc")):
        rep.err(path, "F 类证据必须给 loc")
    if tag == "U" and not _nonempty(ev.get("ref")):
        rep.err(path, "U 类证据必须给可解析 ref（arXiv/DOI/OpenAlex id）")
    if tag == "D" and len(str(ev.get("derivation", "")).strip()) < 20:
        rep.err(path, "D 类证据必须给推导步骤（>=20 字符），不能只写结论")
    if tag == "M":
        sr = _dict(ev, "search_record")
        if not _nonempty(sr.get("queries")):
            rep.err(path + ".search_record.queries", "M 类必须记录查询串")
        if not _nonempty(sr.get("endpoints")):
            rep.err(path + ".search_record.endpoints", "M 类必须记录端点")
        if not _nonempty(sr.get("reason")):
            rep.err(path + ".search_record.reason", "M 类必须记录检索结论/失败原因")
    return tag


def check_parts(data, rep):
    parts = _list(data, "parts")
    if len(parts) < LIMITS["parts"]:
        rep.err("parts", "部件数 %d 过少（<%d），说明远未拆到功能层" % (len(parts), LIMITS["parts"]))
    seen = set()
    groups = set()
    missing = 0
    for i, p in enumerate(parts):
        path = "parts[%d]" % i
        if not isinstance(p, dict):
            rep.err(path, "不是对象")
            continue
        pid = p.get("id")
        if not _nonempty(pid):
            rep.err(path + ".id", "缺失")
        elif pid in seen:
            rep.err(path + ".id", "重复：%s" % pid)
        else:
            seen.add(pid)
        g = p.get("group")
        if g not in GROUPS:
            rep.err(path + ".group", "必须是 R/P/B/M/E/N/G/O/L/T/I/S 之一，实际为 %r" % (g,))
        else:
            groups.add(g)
        for k in ("slot", "name", "io_in", "io_out", "invariant"):
            if not _nonempty(p.get(k)):
                rep.err("%s.%s" % (path, k), "缺失（部件 = I/O 契约 + 不变式，缺一不可）")
        if not _nonempty(p.get("swap_family")) or not isinstance(p.get("swap_family"), list):
            rep.err(path + ".swap_family", "必须有至少一个同族可替换算子，否则未通过交换测试")
        tag = check_evidence(p.get("evidence"), path + ".evidence", rep)
        if tag == "M":
            missing += 1
    rep.note("部件 %d 个，覆盖 %d/12 组" % (len(parts), len(groups)))
    if len(groups) < LIMITS["groups"] - 2:
        rep.err("parts.groups", "只覆盖 %d 组（<%d），提取不完整" % (len(groups), LIMITS["groups"] - 2))
    elif len(groups) < LIMITS["groups"]:
        rep.warn("parts.groups", "只覆盖 %d 组，当前档位建议 >=%d" % (len(groups), LIMITS["groups"]))
    if parts:
        ratio = float(missing) / len(parts)
        if ratio > 0.30:
            rep.warn("parts.evidence", "M 项占比 %.0f%%（>30%%），报告可信度必须降级说明" % (ratio * 100))
    return seen, groups


def check_cost(data, rep):
    cm = _dict(data, "cost_model")
    for k in ("flops_per_unit", "dominant_term"):
        if not _nonempty(cm.get(k)):
            rep.err("cost_model.%s" % k, "缺失（没有成本主项，效率类改进无法证伪）")


def check_upstream(data, rep):
    ups = _list(data, "upstream")
    if not ups:
        rep.warn("upstream", "未记录上游补齐；只有当全部部件证据齐备时才可接受")
    elif len(ups) < LIMITS["upstream"]:
        rep.warn("upstream", "只有 %d 篇，当前档位建议 >=%d" % (len(ups), LIMITS["upstream"]))
    for i, u in enumerate(ups):
        path = "upstream[%d]" % i
        if not isinstance(u, dict):
            rep.err(path, "不是对象")
            continue
        for k in ("id", "title", "fills_gap"):
            if not _nonempty(u.get(k)):
                rep.err("%s.%s" % (path, k), "缺失（上游必须对应一个具体缺口）")
        if u.get("verified") is not True:
            rep.warn(path, "verified != true，发布前请跑 --verify-refs")


def check_downstream(data, rep):
    dns = _list(data, "downstream")
    if len(dns) < LIMITS["downstream"]:
        rep.err("downstream", "只有 %d 篇（<%d），当前档位要求 >=%d" % (len(dns), LIMITS["downstream"], LIMITS["downstream"]))
    mechanisms = set()
    for i, d in enumerate(dns):
        path = "downstream[%d]" % i
        if not isinstance(d, dict):
            rep.err(path, "不是对象")
            continue
        for k in ("id", "title", "addressed_problem", "mechanism", "new_problem"):
            if not _nonempty(d.get(k)):
                rep.err("%s.%s" % (path, k), "缺失")
        if not _nonempty(d.get("new_problem")):
            rep.err(path + ".new_problem", "空 → 说明没抓住结构代价，只看到『性能差一点』")
        m = str(d.get("mechanism", "")).strip().lower()
        if m:
            mechanisms.add(m)
    if dns and len(mechanisms) < 2:
        rep.err("downstream", "所有下游的 mechanism 雷同，说明只找到一条改进路线")


def check_cross_domain(data, rep):
    cds = _list(data, "cross_domain")
    if not cds:
        rep.warn("cross_domain", "未做跨域迁移；三个档位都要求至少 1 条（reject 也算，必须给出裁决理由）")
    for i, c in enumerate(cds):
        path = "cross_domain[%d]" % i
        if not isinstance(c, dict):
            rep.err(path, "不是对象")
            continue
        for k in ("source_field", "problem", "correspondence", "preserved_invariant"):
            if not _nonempty(c.get(k)):
                rep.err("%s.%s" % (path, k), "缺失（类比必须给对象映射与不变式）")
        v = c.get("verdict")
        if v not in VERDICTS:
            rep.err(path + ".verdict", "必须是 admit/weaken/reject，实际为 %r" % (v,))
        if v == "reject" and not _nonempty(c.get("reject_reason")):
            rep.warn(path, "reject 的类比建议写明哪个不变式没保住")


def check_proposals(data, rep, part_index, legacy=False):
    props = _list(data, "proposals")
    if len(props) < LIMITS["proposals"]:
        rep.err("proposals", "只有 %d 条（<%d），当前档位要求 >=%d" % (len(props), LIMITS["proposals"], LIMITS["proposals"]))
    for i, p in enumerate(props):
        path = "proposals[%d]" % i
        if not isinstance(p, dict):
            rep.err(path, "不是对象")
            continue
        fields = PROPOSAL_FIELDS if not legacy else PROPOSAL_FIELDS[:9]
        for k in fields:
            if k == 'changes_shared_parameters' and isinstance(p.get(k), list):
                continue
            if not _nonempty(p.get(k)):
                rep.err("%s.%s" % (path, k), "缺失（提案必填项缺失 = 不可证伪的建议）")
        if p.get("level") not in LEVELS:
            rep.err(path + ".level", "必须是 perturbation/substitution/rearchitecture")
        tp = p.get("targets_part")
        if _nonempty(tp):
            if tp not in part_index:
                rep.err(path + ".targets_part", "指向不存在的部件 %r" % (tp,))
        kc = str(p.get("kill_criterion", ""))
        if kc and not re.search(r"(若|如果|超过|低于|达不到|if|unless|exceed|below)", kc, re.I):
            rep.warn(path + ".kill_criterion", "读起来不像可判定的否定条件，请改成『若 X 超过 Y 则放弃』")


def check_theory(data, rep):
    th = _list(data, "theory")
    layers = set()
    for i, t in enumerate(th):
        path = "theory[%d]" % i
        if not isinstance(t, dict):
            rep.err(path, "不是对象")
            continue
        layer = t.get("layer")
        if layer not in ("L1", "L2", "L3", "L4"):
            rep.err(path + ".layer", "必须是 L1..L4")
        else:
            layers.add(layer)
        ct = t.get("claim_type")
        if ct not in CLAIM_TYPES:
            rep.err(path + ".claim_type", "必须是 theorem/derivation/missing")
        if not _nonempty(t.get("statement")):
            rep.err(path + ".statement", "缺失")
        if ct in ("theorem", "derivation") and not _nonempty(t.get("conditions")):
            rep.err(path + ".conditions",
                    "定理/推导必须重述假设条件；不写明假设等于把结论用在不成立的地方")
        if ct != "missing" and not _nonempty(t.get("source")):
            rep.warn(path + ".source", "缺少来源；若为自证请写明『自证，见推导步骤』")
    for need in ("L1", "L2"):
        if need not in layers:
            rep.err("theory", "缺少 %s 层（函数类实例化 / 表达力与速率）" % need)


def check_gaps(data, rep):
    for i, g in enumerate(_list(data, "gaps")):
        path = "gaps[%d]" % i
        if not isinstance(g, dict):
            rep.err(path, "不是对象")
            continue
        for k in ("item", "queries", "endpoints", "reason", "alternative"):
            if not _nonempty(g.get(k)):
                rep.err("%s.%s" % (path, k), "缺失（失败记录必须可复核）")


def check_report(path, rep, data=None):
    if not os.path.exists(path):
        rep.err("report", "文件不存在：%s" % path)
        return
    text = _read_text_any(path)
    if data is not None:
        from render_report import render
        if text.replace('\r\n', '\n') != render(data):
            rep.err('report', 'Report differs from deterministic JSON projection; regenerate render_report.py')
        else:
            rep.note('report matches anatomy.json')
        return
    for marker, name in REPORT_SECTIONS:
        if marker not in text:
            rep.err("report", "缺少章节 %s %s" % (marker, name))
    words = len(re.findall(r"[\u4e00-\u9fff]", text)) + len(re.findall(r"\b[a-zA-Z]+\b", text))
    if words < 1500:
        rep.warn("report", "篇幅约 %d 字，标准档深度解剖通常 >=2500 字（短于此多半跳过了下游与理论）" % words)
    if "【推断】" not in text and "【推导】" not in text:
        rep.warn("report", "未见【推断】标注；必须区分论文事实与自己的推导")
    rep.note("report 章节齐全，约 %d 字" % words)


# --------------------------------------------------------------------------
# reference verification (network)
# --------------------------------------------------------------------------

UA = {"User-Agent": "archnova/1.0 (checker; contact: local)"}


def _get(url, timeout=25, retries=2):
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            last = "HTTP %s" % exc.code
            if exc.code in (429, 500, 502, 503):
                time.sleep(2 + 3 * attempt)
                continue
            return None
        except Exception as exc:  # noqa: BLE001
            last = type(exc).__name__
            time.sleep(1 + 2 * attempt)
    if last:
        print("  (network note: %s)" % last, file=sys.stderr)
    return None


def _norm_title(s):
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(s).lower())
    return " ".join(s.split())


def _similar(a, b):
    a, b = _norm_title(a), _norm_title(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) / float(max(1, len(ta | tb)))


def resolve_ref(ref):
    """Return (resolved_title, source, url) or (None, reason, None)."""
    ref = str(ref).strip()
    bare = ref
    canonical = canonical_ref(ref)
    if canonical:
        kind, bare = canonical.split(':', 1)
    for prefix in ("arxiv:", "ARXIV:", "arXiv:"):
        if bare.startswith(prefix):
            bare = bare[len(prefix):]
    if OALEX_RE.match(bare) and "openalex" in ref.lower() or OALEX_RE.match(bare):
        wid = bare.rstrip("/").split("/")[-1]
        url = "https://api.openalex.org/works/%s?select=id,title" % wid
        raw = _get(url)
        if not raw:
            return None, "openalex 无响应", None
        try:
            obj = json.loads(raw)
        except Exception:  # noqa: BLE001
            return None, "openalex 返回非 JSON", None
        return obj.get("title"), "openalex", "https://openalex.org/%s" % wid
    if ARXIV_RE.match(bare):
        url = "https://export.arxiv.org/api/query?id_list=%s&max_results=1" % bare
        raw = _get(url)
        if not raw:
            return None, "arxiv 无响应", None
        m = re.search(r"<title>(.*?)</title>", raw, re.S)
        if not m:
            return None, "arxiv 未返回 entry", None
        titles = re.findall(r"<title>(.*?)</title>", raw, re.S)
        t = titles[-1] if len(titles) > 1 else titles[0]
        return re.sub(r"\s+", " ", t).strip(), "arxiv", "https://arxiv.org/abs/%s" % bare
    if DOI_RE.match(bare):
        url = "https://api.crossref.org/works/%s" % urllib.parse.quote(bare)
        raw = _get(url)
        if not raw:
            return None, "crossref 无响应（DOI 可能不存在）", None
        try:
            obj = json.loads(raw)
            t = obj["message"]["title"][0]
        except Exception:  # noqa: BLE001
            return None, "crossref 结构异常", None
        return t, "doi", "https://doi.org/%s" % bare
    return None, "无法识别的标识格式", None


def collect_refs(data):
    sources = {s['id']: s for s in data.get('sources', []) if isinstance(s, dict)}
    refs = []
    primary = sources.get(data.get('paper', {}).get('source_id'), {})
    if primary.get('kind') == 'publication':
        refs.append(('paper.source_id', primary['ref'], primary['title']))
        for kind, value in data.get('paper', {}).get('ids', {}).items():
            if value:
                refs.append(('paper.ids.' + kind, value, data['paper'].get('title')))
    for i, source in enumerate(sources.values()):
        if source.get('kind') == 'publication':
            refs.append(('sources[%d]' % i, source['ref'], source['title']))
    for i, claim in enumerate(data.get('claims', [])):
        for j, ev in enumerate(claim.get('evidence', [])):
            source = sources.get(ev.get('source_id'), {})
            if source.get('kind') == 'publication':
                refs.append(('claims[%d].evidence[%d]' % (i, j), source['ref'], source['title']))
    for i, item in enumerate(data.get('downstream', [])):
        if item.get('id'):
            refs.append(('downstream[%d]' % i, item['id'], item.get('title')))
    #  # (path, ref, expected_title)
    for i, u in enumerate(_list(data, "upstream")):
        if isinstance(u, dict) and _nonempty(u.get("id")):
            refs.append(("upstream[%d]" % i, u["id"], u.get("title")))
    for i, p in enumerate(_list(data, "parts")):
        ev = _dict(p, "evidence") if isinstance(p, dict) else {}
        if ev.get("tag") == "U" and _nonempty(ev.get("ref")):
            refs.append(("parts[%d].evidence" % i, ev["ref"], ev.get("ref_title")))
    for i, p in enumerate(_list(data, "proposals")):
        if isinstance(p, dict):
            for j, r in enumerate(_list(p, "refs")):
                refs.append(("proposals[%d].refs[%d]" % (i, j), r, None))
    for i, t in enumerate(_list(data, "theory")):
        if isinstance(t, dict) and _nonempty(t.get("source")):
            src = str(t["source"])
            if canonical_ref(src):
                refs.append(("theory[%d].source" % i, src, None))
    return refs


def verify_refs(data, rep):
    refs = collect_refs(data)
    if not refs:
        rep.warn("refs", "没有可核验的标识（至少 upstream 应有）")
        return
    seen = {}
    for path, ref, expected in refs:
        key = canonical_ref(ref) or str(ref)
        if key not in seen:
            seen[key] = resolve_ref(ref)
        title, source, url = seen[key]
        if title is None:
            ok, msg = False, "%s 无法解析（%s）" % (ref, source)
        elif expected and _similar(title, expected) < 0.5:
            ok, msg = False, "%s 解析到《%s》，与声明的《%s》不符（疑似编号错误）" % (
                ref, title[:60], str(expected)[:60])
        else:
            ok, msg = True, "%s -> 《%s》 [%s]" % (ref, (title or "")[:70], source)
        (rep.note if ok else rep.err)(path, msg)


def check_crossrefs(data, rep):
    """Cross-field coherence: evidence tags must agree with upstream/gaps/theory."""
    parts = [p for p in _list(data, "parts") if isinstance(p, dict)]
    tags = set((p.get("evidence") or {}).get("tag") for p in parts)
    if parts and "U" not in tags and _list(data, "upstream"):
        rep.warn("parts", "有 upstream 却没有任何部件标 U：由上游补齐定义/数值的部件要标 U，不能一律标 F")
    if _list(data, "gaps") and "M" not in tags:
        rep.warn("parts", "gaps 有 %d 项却没有任何部件标 M：请指明缺的是哪个部件" % len(_list(data, "gaps")))
    th = [t for t in _list(data, "theory") if isinstance(t, dict)]
    if th and not any(t.get("claim_type") == "missing" for t in th):
        rep.warn("theory", "没有 claim_type=missing 的条目：缺哪块理论必须单列一条，否则理论节显得全知")


def check_claims(data, rep, release=False):
    """X6/X7: claim-level provenance. Absent claims[] is a warning unless release."""
    claims = [c for c in _list(data, "claims") if isinstance(c, dict)]
    metrics = [m for m in _list(data, "metrics") if isinstance(m, dict)]
    soft = rep.err if release else rep.warn
    if not claims:
        soft("claims", "没有 claims[]：证据仍是字符串标签，无法验证断言到底被什么支持")
    if not metrics:
        soft("metrics", "没有 metrics[]：target_metric 与 predicted_effect 都无法指向可核查的指标")

    metric_ids = set()
    for i, m in enumerate(metrics):
        p = "metrics[%d]" % i
        for k in ("id", "name", "direction"):
            if not _nonempty(m.get(k)):
                rep.err(p + "." + k, "缺失")
        mid = m.get("id")
        if _nonempty(mid):
            if mid in metric_ids:
                rep.err(p + ".id", "重复的 metric id %r" % (mid,))
            metric_ids.add(mid)

    ids = set()
    ok_direct = set()  # claim_id -> backed by a support=direct paper_fact
    for i, c in enumerate(claims):
        p = "claims[%d]" % i
        for k in ("claim_id", "subject", "predicate", "object", "claim_type"):
            if not _nonempty(c.get(k)):
                rep.err(p + "." + k, "缺失")
        cid = c.get("claim_id")
        if _nonempty(cid):
            cid = str(cid)
            if not cid.startswith("claim:"):
                rep.err(p + ".claim_id", "必须以 claim: 开头（如 claim:attn-scaled-dot）")
            if cid in ids:
                rep.err(p + ".claim_id", "重复的 claim_id %r" % (cid,))
            ids.add(cid)
        ct = c.get("claim_type")
        if ct not in EVIDENCE_CLAIM_TYPES:
            rep.err(p + ".claim_type", "必须是 %s 之一" % "/".join(sorted(EVIDENCE_CLAIM_TYPES)))
        evs = [e for e in _list(c, "evidence") if isinstance(e, dict)]
        if not evs:
            rep.err(p + ".evidence", "至少一条证据项（source_id / locator / support）")
        for j, e in enumerate(evs):
            ep = "%s.evidence[%d]" % (p, j)
            for k in ("source_id", "locator", "support"):
                if not _nonempty(e.get(k)):
                    rep.err(ep + "." + k, "缺失")
            sup = e.get("support")
            if _nonempty(sup) and sup not in SUPPORT_TYPES:
                rep.err(ep + ".support", "必须是 %s 之一" % "/".join(sorted(SUPPORT_TYPES)))
            if sup == "direct" and ct == "paper_fact" and _nonempty(cid):
                ok_direct.add(cid)

    referenced = set()
    for i, p_ in enumerate(_list(data, "parts")):
        if not isinstance(p_, dict):
            continue
        pid = str(p_.get("id") or ("parts[%d]" % i))
        cids = p_.get("claim_ids")
        if cids is None:
            continue
        if not isinstance(cids, list):
            rep.err(pid + ".claim_ids", "必须是数组")
            continue
        for cid in cids:
            if cid not in ids:
                rep.err(pid + ".claim_ids", "引用了不存在的 claim %r" % (cid,))
            else:
                referenced.add(cid)
        tag = (p_.get("evidence") or {}).get("tag")
        if tag == "F" and claims and cids:
            if not any(cid in ok_direct for cid in cids):
                rep.err(pid + ".claim_ids",
                        "标 F 却没有一条 support=direct 的 paper_fact claim 支撑（X7）")
        elif tag == "F" and claims:
            rep.warn(pid + ".claim_ids", "标 F 却未挂任何 claim：证据分级形同虚设（X7）")
    for cid in sorted(ids - referenced):
        rep.warn(cid, "这条 claim 没有被任何部件引用（孤儿证据）")


def check_relations(data, rep, index=None):
    """X2/X4/X8: cross-object references must resolve to something that exists."""
    metrics = set(m["id"] for m in _list(data, "metrics")
                  if isinstance(m, dict) and _nonempty(m.get("id")))
    if metrics:
        for i, pr in enumerate(_list(data, "proposals")):
            if not isinstance(pr, dict):
                continue
            tm = pr.get("target_metric")
            if _nonempty(tm) and tm not in metrics:
                rep.err("proposals[%d].target_metric" % i,
                        "引用了 metrics 里不存在的 %r（先定义指标再引用，X2）" % (tm,))

    gap_ids = set()
    gap_items = []
    for g in _list(data, "gaps"):
        if isinstance(g, dict):
            if _nonempty(g.get("id")):
                gap_ids.add(str(g["id"]))
            if _nonempty(g.get("item")):
                gap_items.append(str(g["item"]))
    m_parts = set()
    for p in _list(data, "parts"):
        if isinstance(p, dict) and (p.get("evidence") or {}).get("tag") == "M":
            if _nonempty(p.get("id")):
                m_parts.add(str(p["id"]))
    for i, u in enumerate(_list(data, "upstream")):
        if not isinstance(u, dict):
            continue
        fg = u.get("fills_gap")
        if not _nonempty(fg) or not (gap_ids or gap_items or m_parts):
            continue
        fg = str(fg)
        if fg in gap_ids or fg in m_parts:
            continue
        if any(fg in t or t in fg for t in gap_items if len(t) >= 4):
            continue
        rep.warn("upstream[%d].fills_gap" % i,
                 "%r 既不匹配 gaps[].id、也不匹配 M 部件的 id、也不像某条 gaps[].item（X4）" % (fg,))

    cm = _dict(data, "cost_model")
    dom = cm.get("dominant_term")
    parts = index or {}
    cd = sorted(k for k, v in parts.items() if v.get("cost_dominant"))
    if _nonempty(dom) and cd and not any(k in str(dom) for k in cd):
        rep.err("cost_model.dominant_term",
                "没有指向任何 cost_dominant 部件（%s），主项归属无法核对（X8）" % ", ".join(cd))


def check_stage(data, rep, release=False):
    """X11: the eight stages must be a state machine, not prose."""
    st = _dict(data, "stage")
    if not st:
        soft = rep.err if release else rep.warn
        soft("stage", "没有 stage 对象：八阶段走到哪一步无法核查（stage/stage_status/blocking_items）")
        return
    if not _nonempty(st.get("stage")):
        rep.err("stage.stage", "缺失（应为 G0–G8）")
    status = st.get("stage_status")
    if status not in STAGE_STATUS:
        rep.err("stage.stage_status", "必须是 %s 之一" % "/".join(sorted(STAGE_STATUS)))
    if status == "blocked" and not _nonempty(st.get("blocking_items")):
        rep.err("stage.blocking_items", "blocked 状态必须列出 blocking_items")
    if release and (status != "passed" or st.get("stage") != "G8" or st.get("blocking_items")):
        rep.err("stage.stage_status", "release 模式要求 stage_status=passed，当前 %r" % (status,))


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate an archnova result.")
    ap.add_argument("anatomy", help="path to anatomy.json")
    ap.add_argument("--report", help="path to report.md")
    ap.add_argument("--verify-refs", action="store_true", help="resolve every arXiv/DOI id online")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--legacy", action="store_true", help="explicit v1 structural review only; cannot release")
    ap.add_argument("--release", action="store_true",
                    help="release mode: claims/metrics/stage required, warnings block, refs verified")
    ap.add_argument("--release-mode", choices=["honest_report","supported_conclusions"], help="Must agree with document publication.mode")
    ap.add_argument("--depth", choices=["lite", "standard", "deep"], default=None,
                    help="minimums per depth tier (default: standard)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable result")
    args = ap.parse_args(argv)
    _force_utf8()
    

    if not os.path.exists(args.anatomy):
        print("[ERROR] anatomy file not found: %s" % args.anatomy)
        return 2
    try:
        data = json.loads(_read_text_any(args.anatomy))
    except Exception as exc:  # noqa: BLE001
        print("[ERROR] cannot parse JSON: %s" % exc)
        return 2
    if not isinstance(data, dict):
        print("[ERROR] top-level JSON must be an object")
        return 2

    rep = Report()
    version = data.get('schema_version')
    legacy = version is None and args.legacy
    if legacy:
        rep.warn('schema_version', 'Legacy structural review only; use migrate_anatomy.py and fill missing evidence')
    elif version != ONTOLOGY_VERSION:
        rep.err('schema_version', 'Expected %s; v1 requires --legacy or explicit migration' % ONTOLOGY_VERSION)
    elif args.legacy:
        rep.err('schema_version', '--legacy is only for unversioned v1 data')
    if args.release and legacy:
        rep.err('release', 'Legacy documents cannot be released')
    if not legacy and not rep.errors:
        schema_check(data, rep)
    if rep.errors:
        return emit_result(rep, args, refs_checked=False)
    if args.release_mode and args.release_mode != data.get('publication',{}).get('mode'):
        rep.err('publication.mode','CLI release mode disagrees with document')
    depth = args.depth or data.get('depth', 'standard')
    if args.depth and data.get('depth') and args.depth != data['depth']:
        rep.err('depth', 'CLI depth disagrees with document depth')
    LIMITS.update(DEPTH_LIMITS[depth])
    check_paper(data, rep)
    check_core(data, rep)
    check_contract(data, rep)
    part_index, groups = check_parts(data, rep)
    index = {}
    for p in _list(data, "parts"):
        if isinstance(p, dict) and _nonempty(p.get("id")):
            index[p["id"]] = {
                "cost_dominant": p.get("cost_dominant") is True,
            }
    check_cost(data, rep)
    check_upstream(data, rep)
    check_downstream(data, rep)
    check_cross_domain(data, rep)
    check_proposals(data, rep, index, legacy=legacy)
    check_theory(data, rep)
    check_gaps(data, rep)
    check_crossrefs(data, rep)
    if not legacy:
        check_claims(data, rep, args.release)
        check_relations(data, rep, index)
        check_stage(data, rep, args.release)
        check_graph(data, rep, args.release)
        check_architecture(data, rep, args.release)
        check_snapshots(data, rep, os.path.dirname(os.path.abspath(args.anatomy)), args.release)
        check_numeric(data, rep)
        from github_repos import check_discoveries
        check_discoveries(data, rep)
        from repository_coverage import check_explorations
        args.repository_summary = check_explorations(data, rep, args.release)
        from counterevidence import check_counterevidence
        args.counterevidence_summary = check_counterevidence(data, rep, os.path.dirname(os.path.abspath(args.anatomy)), args.release)
        args.semantic_summary = check_reviews(data, rep, os.path.dirname(os.path.abspath(args.anatomy)), args.release)
        from experiment_runner import check_experiment_receipts
        args.experiment_summary = check_experiment_receipts(data, rep, os.path.dirname(os.path.abspath(args.anatomy)))
        check_receipts(data, rep, args.release)
    if args.report:
        check_report(args.report, rep, None if legacy else data)
    if args.release and not args.report:
        rep.err('release', '--report is required for the final report consistency gate')
    args.local_validation_passed = not rep.errors
    refs_checked = False
    if (args.verify_refs or args.release) and not rep.errors:
        verify_refs(data, rep)
        refs_checked = True
    return emit_result(rep, args, refs_checked)


def emit_result(rep, args, refs_checked=False):
    failed = (bool(rep.errors)
              or ((args.strict or args.release) and bool(rep.warnings)))
    if args.json:
        print(json.dumps({
            "passed": not failed,
            "validation_scope": {
                "structure_and_relations": ("legacy_review_only" if args.legacy else
                    ("passed" if getattr(args, 'local_validation_passed', not rep.errors) else "failed")),
                "reference_resolution": (("passed" if not rep.errors else "failed") if refs_checked else "not_run"),
                "claim_entailment": getattr(args,'semantic_summary',{}).get('citation',{'status':'not_run'}),
                "counterevidence": getattr(args,'counterevidence_summary',{}),
                "implementation_experiments": getattr(args,'experiment_summary',{}),
                "repository_exploration": getattr(args,'repository_summary',{}),
                "publication": getattr(args,'semantic_summary',{}).get('publication',{}),
                "effective_verdicts": getattr(args,'semantic_summary',{}).get('effective_verdicts',[]),
                "mathematical_review": getattr(args,'semantic_summary',{}).get('mathematics',{'status':'not_run'}),
                "formal_proof_scope": "only separately reported exact rational identities",
                "research_conclusions": "not_verified"},
            "errors": rep.errors,
            "warnings": rep.warnings,
            "notes": rep.notes,
        }, ensure_ascii=False, indent=2))
    else:
        for line in rep.errors + rep.warnings + rep.notes:
            print(line)
        print("")
        print("RESULT: %s  (%d errors, %d warnings)" % (
            "PASS" if not failed else "FAIL", len(rep.errors), len(rep.warnings)))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
