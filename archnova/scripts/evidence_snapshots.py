# -*- coding: utf-8 -*-
"""Local immutable evidence receipts; exact Unicode spans, no PDF interpretation."""
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime


def bundled_path(root, relative):
    path=Path(relative)
    if path.is_absolute() or re.match(r'^[A-Za-z]:',relative) or '\\' in relative:
        raise ValueError('Snapshot paths must be portable relative paths')
    root=Path(root).resolve();resolved=(root/path).resolve()
    try:resolved.relative_to(root)
    except ValueError:raise ValueError('Snapshot path escapes document bundle')
    if not resolved.is_file():raise ValueError('Missing snapshot file: '+relative)
    return resolved


def iso_time(value):
    try:
        if not isinstance(value,str) or 'T' not in value:raise ValueError()
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.tzinfo is None:raise ValueError()
    except (ValueError,TypeError):raise ValueError('retrieved_at requires an ISO timestamp with timezone')


def load_snapshot(snapshot,root):
    iso_time(snapshot['extraction']['retrieved_at'])
    for path_key,hash_key in [('original_path','original_sha256'),('text_path','text_sha256')]:
        body=bundled_path(root,snapshot[path_key]).read_bytes()
        if hashlib.sha256(body).hexdigest()!=snapshot[hash_key]:raise ValueError('Snapshot hash mismatch: '+path_key)
    try:return bundled_path(root,snapshot['text_path']).read_bytes().decode('utf-8')
    except UnicodeDecodeError:raise ValueError('Extracted text must be exact UTF-8')


def verify_evidence_item(evidence,snapshot,root,text=None):
    if evidence['snapshot_id']!=snapshot['id'] or evidence['source_id']!=snapshot['source_id']:
        raise ValueError('Snapshot/source identity mismatch')
    if evidence.get('content_hash')!=snapshot['text_sha256']:
        raise ValueError('Evidence content_hash must equal extracted text hash')
    text=load_snapshot(snapshot,root) if text is None else text
    start,end=evidence['span']['start'],evidence['span']['end']
    if any(isinstance(x,bool) or not isinstance(x,int) for x in (start,end)) or not 0<=start<end<=len(text):
        raise ValueError('Invalid Unicode half-open quote span')
    if not evidence.get('quote') or text[start:end]!=evidence['quote']:
        raise ValueError('Quote does not match extracted UTF-8 text at the declared span')
    return True


def check_snapshots(data,rep,root,release=False):
    registry={};texts={};sources={s['id']:s for s in data['sources']}
    for snapshot in data['evidence_snapshots']:
        sid=snapshot['id']
        if sid in registry:rep.err('evidence_snapshots','Duplicate id: '+sid)
        registry[sid]=snapshot
        if snapshot['source_id'] not in sources:rep.err(sid,'Unknown source_id')
        try:texts[sid]=load_snapshot(snapshot,root)
        except (ValueError,OSError,KeyError) as exc:rep.err(sid,str(exc))
    for claim in data['claims']:
        for i,ev in enumerate(claim['evidence']):
            path=claim['claim_id']+'.evidence[%d]'%i
            if 'snapshot_id' in ev:
                sid=ev['snapshot_id']
                if sid not in registry:rep.err(path,'Unknown snapshot_id');continue
                if sid not in texts:continue
                try:verify_evidence_item(ev,registry[sid],root,texts[sid])
                except (ValueError,KeyError,TypeError) as exc:rep.err(path,str(exc))
            elif release and sources.get(ev['source_id'],{}).get('kind')=='publication':
                rep.err(path,'Publication evidence requires a verified snapshot and exact quote span')
            if release and claim['claim_type'] in ('paper_fact','upstream_fact'):
                try:iso_time(ev.get('retrieved_at'))
                except ValueError as exc:rep.err(path,str(exc))


def snapshot_receipt(original,text,root,source_id,snapshot_id,source_version,tool,tool_version,retrieved_at):
    root=Path(root).resolve()
    def relative(path):
        try:return Path(path).resolve().relative_to(root).as_posix()
        except ValueError:raise ValueError('Snapshot files must be inside the document bundle')
    receipt={'id':snapshot_id,'source_id':source_id,'source_version':source_version,
             'original_path':relative(original),'original_sha256':hashlib.sha256(Path(original).read_bytes()).hexdigest(),
             'text_path':relative(text),'text_sha256':hashlib.sha256(Path(text).read_bytes()).hexdigest(),
             'extraction':{'tool':tool,'version':tool_version,'retrieved_at':retrieved_at}}
    load_snapshot(receipt,root)
    return receipt


def main():
    import argparse
    ap=argparse.ArgumentParser(description='Create a receipt for already saved original and UTF-8 extraction files; never downloads or extracts documents')
    for name in ('original','text','bundle','source-id','snapshot-id','source-version','tool','tool-version','retrieved-at','output'):
        ap.add_argument('--'+name,required=True)
    a=ap.parse_args();target=Path(a.output)
    if target.exists():ap.error('Choose a new output file')
    try:receipt=snapshot_receipt(a.original,a.text,a.bundle,a.source_id,a.snapshot_id,a.source_version,a.tool,a.tool_version,a.retrieved_at)
    except (ValueError,OSError) as exc:ap.error(str(exc))
    target.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(str(target))
if __name__=='__main__':main()
