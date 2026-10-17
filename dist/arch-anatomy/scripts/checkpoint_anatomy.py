# -*- coding: utf-8 -*-
"""Revalidate a complete draft and checkpoint its local artifacts.

Receipts detect stale files. They are neither signatures nor evidence entailment proofs.
Network resolution and final report consistency are separate release checks.
"""
import argparse
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
from validation_core import STAGE_FIELDS, stage_digest


def finalize(original, bundle_root=None):
    from check_anatomy import main as check
    if original.get('stage', {}).get('blocking_items'):
        return None, {'passed': False, 'errors': ['Unresolved blocking_items; review them before checkpointing'], 'warnings': []}
    data = copy.deepcopy(original)
    data['stage'] = {'stage': 'G8', 'stage_status': 'passed',
                     'blocking_items': [], 'receipts': []}
    data['stage']['receipts'] = [
        {'stage': sid, 'status': 'passed', 'digest': stage_digest(data, sid)}
        for sid in STAGE_FIELDS]
    with tempfile.TemporaryDirectory() as tmp:
        if original.get('evidence_snapshots'):
            if bundle_root is None:
                return None, {'passed':False, 'errors':['bundle_root is required for evidence snapshot verification'], 'warnings':[]}
            from check_anatomy import Report
            from evidence_snapshots import check_snapshots
            rep = Report()
            check_snapshots(original, rep, bundle_root)
            if rep.errors:
                return None, {'passed':False,'errors':rep.errors,'warnings':rep.warnings}
            # Preserve relative bundle paths without copying original documents to a temp dir.
            path = Path(bundle_root) / ('.anatomy-check-' + Path(tmp).name + '.json')
        else:
            path = Path(tmp) / 'candidate.json' 
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                rc = check([str(path), '--strict', '--json'])
            finally:
                if original.get('evidence_snapshots'):
                    path.unlink()
        result = json.loads(out.getvalue())
    return (data if rc == 0 else None), result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('anatomy')
    ap.add_argument('-o', '--output', required=True)
    a = ap.parse_args(argv)
    target = Path(a.output)
    if target.exists():
        ap.error('Choose a new output file')
    original = json.loads(Path(a.anatomy).read_text(encoding='utf-8-sig'))
    if original.get('evidence_snapshots') and target.resolve().parent != Path(a.anatomy).resolve().parent:
        ap.error('Keep checkpoint output beside the draft so snapshot paths remain valid')
    data, result = finalize(original, Path(a.anatomy).resolve().parent)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if data is None:
        return 1
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
