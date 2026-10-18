"""Schema and graph invariants. Resolving a reference never proves its claim."""
import hashlib
import json
import re
from pathlib import Path

STAGE_FIELDS = {
    'G0': ['paper', 'sources', 'core_architecture', 'evidence_snapshots'],
    'G1': ['interface_contract', 'parts', 'claims', 'dataflow', 'ablations', 'interactions'],
    'G2': ['cost_model'], 'G3': ['upstream', 'gaps'],
    'G4': ['downstream'], 'G5': ['cross_domain'],
    'G6': ['theory', 'mathematical_checks'], 'G7': ['proposals', 'metrics', 'repository_discoveries', 'repository_explorations', 'implementation_experiments'],
    'G8': ['schema_version', 'depth', 'semantic_reviews', 'publication', 'counterevidence_searches'],
}


def stage_digest(data, stage):
    """Cumulative artifact digest; any changed input invalidates downstream gates."""
    fields = []
    for key in STAGE_FIELDS:
        fields.extend(STAGE_FIELDS[key])
        if key == stage:
            break
    payload = {k: data.get(k) for k in fields}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def schema_check(data, rep):
    try:
        from jsonschema import Draft4Validator
    except ImportError:
        rep.err('schema', 'Install requirements.txt: jsonschema is required; validation fails closed')
        return False
    schema = json.loads((Path(__file__).resolve().parents[1] / 'assets/anatomy.schema.json').read_text(encoding='utf-8'))
    errors = sorted(Draft4Validator(schema).iter_errors(data),
                    key=lambda e: '/'.join(str(v) for v in e.path))
    for error in errors:
        path = '.'.join(str(v) for v in error.path) or '$'
        rep.err('schema.' + path, error.message)
    return not errors


def canonical_ref(value):
    value = str(value).strip()
    value = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', value, flags=re.I)
    value = re.sub(r'^doi:', '', value, flags=re.I)
    value = re.sub(r'^https?://arxiv\.org/(?:abs|pdf)/', '', value, flags=re.I)
    value = re.sub(r'^arxiv:', '', value, flags=re.I)
    if value.endswith('.pdf'):
        value = value[:-4]
    if re.match(r'^\d{4}\.\d{4,5}(v\d+)?$', value):
        return 'arxiv:' + value
    if re.match(r'^10\.\d{4,9}/\S+$', value):
        return 'doi:' + value.lower()
    if re.match(r'^(https?://openalex.org/)?W\d+$', value):
        return 'openalex:' + value.rsplit('/', 1)[-1]
    return None


def check_graph(data, rep, release=False):
    sources = {}
    for source in data['sources']:
        sid = source['id']
        if sid in sources:
            rep.err('sources', 'Duplicate source id: ' + sid)
        sources[sid] = source
        if source['kind'] == 'publication' and not canonical_ref(source.get('ref', '')):
            rep.err('sources.' + sid, 'Publication requires a resolvable arXiv/DOI/OpenAlex ref')
        if release and source['kind'] == 'synthetic':
            rep.err('sources.' + sid, 'Synthetic fixtures cannot be released as research evidence')
    primary = data['paper']['source_id']
    if primary not in sources:
        rep.err('paper.source_id', 'Unknown source: ' + primary)
    elif sources[primary]['kind'] == 'publication':
        refs = {canonical_ref(v) for v in data['paper']['ids'].values() if v}
        if canonical_ref(sources[primary].get('ref', '')) not in refs:
            rep.err('paper.source_id', 'Primary source ref must match paper.ids')
    if release and (primary not in sources or sources[primary]['kind'] != 'publication'):
        rep.err('paper.source_id', 'Release primary source must be a publication')
    from ontology_gen import SLOT_GROUP, LAYERS
    parts = {p['id']: p for p in data['parts']}
    for part in data['parts']:
        if SLOT_GROUP.get(part['slot']) != part['group']:
            rep.err(part['id'], 'slot does not belong to group')
        if 'layer' in part and part['group'] not in LAYERS.get(part['layer'], []):
            rep.err(part['id'], 'group does not belong to layer')
    claims = {c['claim_id']: c for c in data['claims']}
    for claim in data['claims']:
        if claim['subject'] not in parts:
            rep.err(claim['claim_id'], 'Unknown part subject: ' + claim['subject'])
        for ev in claim['evidence']:
            if ev['source_id'] not in sources:
                rep.err(claim['claim_id'], 'Unknown evidence source: ' + ev['source_id'])
            if release and claim['claim_type'] in ('paper_fact', 'upstream_fact'):
                if sources.get(ev['source_id'], {}).get('kind') != 'publication':
                    rep.err(claim['claim_id'], 'Publication evidence requires a publication source')
                for key in ('quote', 'retrieved_at', 'content_hash'):
                    if not ev.get(key):
                        rep.err(claim['claim_id'], 'Release evidence requires ' + key)
                if ev.get('content_hash') and not re.match(r'^[a-f0-9]{64}$', ev['content_hash']):
                    rep.err(claim['claim_id'], 'content_hash must be SHA-256')
    for pid, part in parts.items():
        attached = []
        for cid in part['claim_ids']:
            claim = claims.get(cid)
            if not claim:
                continue  # check_claims reports unresolved identifiers
            if claim['subject'] != pid:
                rep.err(pid, 'Claim subject does not match part: ' + cid)
            attached.append(claim)
        tag = part['evidence']['tag']
        expected = {'F': 'paper_fact', 'U': 'upstream_fact', 'D': 'derivation'}.get(tag)
        if expected and not any(c['claim_type'] == expected and any(
                e['support'] == 'direct' and (tag != 'F' or e['source_id'] == primary)
                for e in c['evidence']) for c in attached):
            rep.err(pid, 'No matching direct claim/source for evidence tag ' + tag)
    dominant = data['cost_model']['dominant_part_ids']
    if not any(p['cost_dominant'] for p in parts.values()):
        rep.err('cost_model', 'No cost_dominant part declared')
    for pid in dominant:
        if pid not in parts or not parts[pid]['cost_dominant']:
            rep.err('cost_model.dominant_part_ids', 'Not a cost_dominant part: ' + pid)
    gaps = [g['id'] for g in data['gaps']]
    if len(set(gaps)) != len(gaps):
        rep.err('gaps', 'Duplicate gap ids')
    missing = {p['id'] for p in parts.values() if p['evidence']['tag'] == 'M'}
    for upstream in data['upstream']:
        if upstream['fills_gap'] not in set(gaps) | missing:
            rep.err('upstream.fills_gap', 'Expected exact gap/part id: ' + upstream['fills_gap'])
    metrics = {m['id'] for m in data['metrics']}
    for proposal in data['proposals']:
        if proposal['target_metric'] not in metrics:
            rep.err('proposals.target_metric', 'Unknown metric id')


def check_receipts(data, rep, release=False):
    st = data['stage']
    current = st['stage']
    if current not in STAGE_FIELDS:
        rep.err('stage.stage', 'Unknown stage')
        return
    if release and (current != 'G8' or st['stage_status'] != 'passed' or st['blocking_items']):
        rep.err('stage', 'Release requires G8/passed and no blocking items')
    receipts = {}
    for receipt in st['receipts']:
        sid = receipt['stage']
        if sid in receipts:
            rep.err('stage.receipts', 'Duplicate receipt: ' + sid)
        receipts[sid] = receipt
        if sid not in STAGE_FIELDS or receipt['digest'] != stage_digest(data, sid):
            rep.err('stage.receipts', 'Stale/invalid artifact digest: ' + sid)
    position = list(STAGE_FIELDS).index(current)
    required = list(STAGE_FIELDS)[:position + (st['stage_status'] == 'passed')]
    for sid in required:
        if sid not in receipts:
            rep.err('stage.receipts', 'Missing prerequisite receipt: ' + sid)
    for sid in receipts:
        if sid in STAGE_FIELDS and list(STAGE_FIELDS).index(sid) > position:
            rep.err('stage.receipts', 'Receipt ahead of current stage: ' + sid)
