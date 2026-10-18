# -*- coding: utf-8 -*-
"""Account for each proposal's implementation exploration, including honest failures."""
import hashlib,json

def target_hash(data,proposal):
    snapshot={'target':proposal,'interface_contract':data.get('interface_contract'),
              'dataflow':data.get('dataflow'),'parts':data.get('parts')}
    return hashlib.sha256(json.dumps(snapshot,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()

def check_explorations(data,rep,release=False):
    proposals={p['id']:p for p in data.get('proposals',[])};seen=set();discoveries={}
    for discovery in data.get('repository_discoveries',[]):
        if discovery.get('plan_hash') in discoveries:rep.err('repository_discoveries','Duplicate discovery plan hash')
        discoveries[discovery.get('plan_hash')]=discovery
    for item in data.get('repository_explorations',[]):
        pid=item['proposal_id'];status=item['status']
        if pid not in proposals or pid in seen:rep.err('repository_explorations','Unknown or duplicate proposal: '+pid);continue
        seen.add(pid)
        if item['target_snapshot_hash']!=target_hash(data,proposals[pid]):rep.err(pid,'Exploration target/interface changed; repeat or explicitly reassess search')
        if not item.get('reason','').strip():rep.err(pid,'Exploration needs a concrete reason/result')
        selected=[]
        for key in item['discovery_plan_hashes']:
            found=discoveries.get(key)
            if found is None or found.get('plan',{}).get('target_id')!=pid:rep.err(pid,'Exploration refers to missing or different-target discovery')
            else:selected.append(found)
        if status!='skipped' and not selected:rep.err(pid,'Searched/no-result/unavailable states require an actual discovery receipt')
        if status=='searched' and not any(d.get('candidates') for d in selected):rep.err(pid,'searched status needs actual candidates; otherwise report not_found/unavailable')
        if status=='not_found' and (not selected or any(d.get('status')!='not_found' for d in selected)):rep.err(pid,'not_found requires completed zero-result searches')
        if status=='unavailable' and (not selected or not any(d.get('status') in ('unavailable','partial') for d in selected)):rep.err(pid,'unavailable requires an actual retrieval failure receipt')
        if status=='skipped' and item['discovery_plan_hashes']:rep.err(pid,'Skipped exploration cannot claim completed search receipts')
    missing=sorted(set(proposals)-seen)
    if release:
        for pid in missing:rep.err(pid,'Missing repository exploration record; search, report failure, or justify skipping')
    return {'required':len(proposals),'accounted':len(seen),'missing':missing,'status':'complete' if not missing else 'pending'}


def main(argv=None):
    import argparse
    from pathlib import Path
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('anatomy');ap.add_argument('--proposal',required=True)
    ap.add_argument('--status',choices=['searched','not_found','unavailable','skipped'],required=True)
    ap.add_argument('--reason',required=True);ap.add_argument('--discovery',action='append',default=[]);ap.add_argument('-o','--output',required=True)
    a=ap.parse_args(argv);target=Path(a.output)
    if target.exists():ap.error('Choose a new output file')
    data=json.loads(Path(a.anatomy).read_text(encoding='utf-8-sig'));proposal=next((p for p in data['proposals'] if p['id']==a.proposal),None)
    if proposal is None:ap.error('Unknown proposal')
    discoveries=[json.loads(Path(p).read_text(encoding='utf-8-sig')) for p in a.discovery]
    existing={d['plan_hash'] for d in data['repository_discoveries']}
    data['repository_discoveries'].extend(d for d in discoveries if d['plan_hash'] not in existing)
    item={'proposal_id':a.proposal,'status':a.status,'reason':a.reason,'discovery_plan_hashes':[d['plan_hash'] for d in discoveries],
          'target_snapshot_hash':target_hash(data,proposal)}
    data['repository_explorations']=[e for e in data.get('repository_explorations',[]) if e['proposal_id']!=a.proposal]+[item]
    from check_anatomy import Report
    from github_repos import check_discoveries
    rep=Report();check_discoveries(data,rep);check_explorations(data,rep)
    if rep.errors:print('\n'.join(rep.errors));return 1
    blockers=data.get('stage',{}).get('blocking_items',[])
    data['stage']={'stage':'G8','stage_status':'blocked' if blockers else 'pending','blocking_items':blockers,'receipts':[]}
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(str(target));return 0
if __name__=='__main__':raise SystemExit(main())
