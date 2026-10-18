# -*- coding: utf-8 -*-
"""Bounded adversarial searches and source-grounded opposing-evidence review."""
import argparse,hashlib,json,re,urllib.parse,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
from proof_dependencies import target_registry
from evidence_snapshots import load_snapshot,verify_evidence_item,iso_time
from validation_core import canonical_ref

def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def registry(data):
    rows=target_registry(data)+[(p['id'],p) for p in data.get('parts',[])]+[(p['id'],p) for p in data.get('proposals',[])]
    return dict(rows)
def context_hash(data,target_id):
    targets=registry(data)
    if target_id not in targets:raise ValueError('Unknown counterevidence target: '+target_id)
    return digest({'target':targets[target_id],'interface':data.get('interface_contract'),'dataflow':data.get('dataflow')})
def validate_plan(plan,data):
    if not isinstance(plan,dict) or not isinstance(plan.get('rationale'),str) or not plan['rationale'].strip():raise ValueError('Explain the falsification or boundary-condition search')
    context_hash(data,plan.get('target_id'))
    queries=plan.get('queries')
    if not isinstance(queries,list) or not 1<=len(queries)<=4:raise ValueError('Use 1..4 adversarial queries')
    for query in queries:
        if query.get('provider') not in ('crossref','arxiv') or query.get('intent') not in ('limitation','failure','contradiction','replication'):raise ValueError('Queries require an adversarial intent and supported provider')
        if not isinstance(query.get('query'),str) or not query['query'].strip() or len(query['query'])>500:raise ValueError('Use bounded concrete queries')
    return plan

def endpoint(query,limit):
    if query['provider']=='crossref':
        return 'https://api.crossref.org/works?'+urllib.parse.urlencode({'query':query['query'],'rows':limit,'select':'DOI,title,abstract,URL'})
    return 'https://export.arxiv.org/api/query?'+urllib.parse.urlencode({'search_query':'all:'+query['query'],'start':0,'max_results':limit})

def fetch(url):
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in ('api.crossref.org','export.arxiv.org'):raise ValueError('Only fixed read-only literature API hosts are supported')
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'archnova-counterevidence/2.5'})
        with urllib.request.urlopen(request,timeout=12) as response:
            raw=response.read(3*1024*1024+1)
            if len(raw)>3*1024*1024:raise ValueError('Counter-search response budget exceeded')
            text=raw.decode('utf-8')
        return {'ok':True,'url':url,'observed_at':now(),'raw_text':text,'response_sha256':hashlib.sha256(raw).hexdigest()}
    except urllib.error.HTTPError as exc:return {'ok':False,'url':url,'observed_at':now(),'status':exc.code,'error':'HTTP '+str(exc.code)}
    except (OSError,ValueError,UnicodeError) as exc:return {'ok':False,'url':url,'observed_at':now(),'status':None,'error':type(exc).__name__}

def parse_candidates(query,response,limit):
    if not response.get('ok'):return []
    raw=response.get('raw_text')
    if not isinstance(raw,str) or len(raw.encode('utf-8'))>3*1024*1024 or hashlib.sha256(raw.encode('utf-8')).hexdigest()!=response.get('response_sha256'):raise ValueError('Counter-search raw response hash mismatch')
    records=[]
    if query['provider']=='crossref':
        body=json.loads(raw)
        for item in body['message']['items'][:limit]:
            doi=item.get('DOI');title=item.get('title') or []
            if not isinstance(doi,str) or not doi or not title:continue
            records.append({'id':'doi:'+doi.lower(),'title':title[0],'abstract':item.get('abstract',''),'url':item.get('URL'),'provider':'crossref'})
    else:
        import xml.etree.ElementTree as ET
        ns={'a':'http://www.w3.org/2005/Atom'}
        tree=ET.fromstring(raw)
        for entry in tree.findall('a:entry',ns)[:limit]:
            url=entry.findtext('a:id','',ns);identifier=url.rsplit('/',1)[-1]
            if not re.fullmatch(r'\d{4}\.\d{4,5}(?:v\d+)?',identifier):continue
            records.append({'id':'arxiv:'+identifier,'title':' '.join(entry.findtext('a:title','',ns).split()),
                'abstract':entry.findtext('a:summary','',ns),'url':url,'provider':'arxiv'})
    return records

def search(plan,data,limit=3):
    validate_plan(plan,data)
    if type(limit)!=int or not 1<=limit<=5:raise ValueError('Search limit must be 1..5 per query')
    retrievals=[];candidates={};failed=False
    for query in plan['queries']:
        url=endpoint(query,limit);response=fetch(url)
        try:records=parse_candidates(query,response,limit)
        except (ValueError,KeyError,TypeError) as exc:
            response={'ok':False,'url':url,'observed_at':now(),'error':'Unusable response: '+str(exc)};records=[]
        if not response.get('ok'):failed=True
        retrievals.append({'query':query,'response':response})
        for record in records:candidates.setdefault(record['id'],record)
    result={'id':'counter:'+digest({'plan':plan,'retrievals':retrievals})[:24],'plan':plan,
        'target_hash':context_hash(data,plan['target_id']),'limit':limit,'retrievals':retrievals,
        'candidates':list(candidates.values()),'status':('partial' if candidates else 'unavailable') if failed else ('searched' if candidates else 'not_found'),
        'limitation':'Candidate metadata is a retrieval lead, not evidence of contradiction; original source snapshots must support classifications'}
    result['input_hash']=digest(result);return result

def validate_search(result,data):
    validate_plan(result['plan'],data)
    if result.get('target_hash')!=context_hash(data,result['plan']['target_id']):raise ValueError('Counter-search target or interface changed')
    payload={k:v for k,v in result.items() if k not in ('input_hash','review')}
    if digest(payload)!=result.get('input_hash'):raise ValueError('Counter-search receipt changed')
    limit=result['limit']
    if type(limit)!=int or not 1<=limit<=5 or len(result['retrievals'])!=len(result['plan']['queries']):raise ValueError('Counter-search retrieval coverage/budget invalid')
    candidates={};failed=False
    for query,retrieval in zip(result['plan']['queries'],result['retrievals']):
        response=retrieval['response']
        if retrieval['query']!=query or response.get('url')!=endpoint(query,limit):raise ValueError('Counter-search query/endpoint mismatch')
        iso_time(response.get('observed_at'))
        if not response.get('ok'):failed=True
        for item in parse_candidates(query,response,limit):candidates.setdefault(item['id'],item)
    expected_status=(('partial' if candidates else 'unavailable') if failed else ('searched' if candidates else 'not_found'))
    if list(candidates.values())!=result['candidates'] or result['status']!=expected_status:raise ValueError('Stored candidates/status disagree with raw retrievals')
    return True

def validate_assessments(search_result,review,data,root):
    if review.get('search_hash')!=search_result['input_hash']:raise ValueError('Counterevidence review is stale')
    who=review.get('reviewer',{})
    if not who.get('identity') or not who.get('model'):raise ValueError('Record counterevidence reviewer identity/model')
    iso_time(review.get('reviewed_at'));candidates={c['id']:c for c in search_result['candidates']};seen=set();material=[]
    snapshots={s['id']:s for s in data.get('evidence_snapshots',[])};sources={s['id']:s for s in data.get('sources',[])}
    for assessment in review.get('assessments',[]):
        cid=assessment.get('candidate_id');classification=assessment.get('classification')
        if cid not in candidates or cid in seen:raise ValueError('Unknown or duplicate counterevidence candidate')
        seen.add(cid)
        if classification not in ('opposing','limiting','supporting','irrelevant','unresolved'):raise ValueError('Unknown candidate classification')
        if not isinstance(assessment.get('rationale'),str) or not assessment['rationale'].strip():raise ValueError('Explain each counterevidence assessment')
        evidence=assessment.get('evidence')
        if not isinstance(evidence,list):raise ValueError('Assessment needs explicit evidence[]')
        if classification in ('opposing','limiting','supporting') and not evidence:raise ValueError('Scientific classifications need verified original-source evidence')
        for i,item in enumerate(evidence):
            snapshot=snapshots.get(item.get('snapshot_id'));source=sources.get(item.get('source_id'))
            if not snapshot or not source:raise ValueError('Opposing evidence needs a registered source and snapshot')
            if canonical_ref(source.get('ref',''))!=canonical_ref(cid):raise ValueError('Evidence source does not match the retrieved candidate identity')
            text=load_snapshot(snapshot,root);verify_evidence_item(item,snapshot,root,text)
            start,end=item['span']['start'],item['span']['end']
            if end-start>12000:raise ValueError('Counterevidence quote too large; split it')
            material.append({'id':search_result['id']+':'+cid+':evidence:'+str(i),'source_id':source['id'],
                'candidate_id':cid,'classification':classification,'rationale':assessment['rationale'],'quote':item['quote'],
                'span':item['span'],'snapshot':snapshot,'source':source,
                'context_before':text[max(0,start-1200):start],'context_after':text[end:end+1200]})
    if seen!=set(candidates):raise ValueError('Every retrieved candidate must be assessed; do not omit inconvenient results')
    return material

def counter_material(data,target_id,root):
    evidence=[];reviews=[];issues=[]
    for result in data.get('counterevidence_searches',[]):
        if result.get('plan',{}).get('target_id')!=target_id:continue
        try:
            validate_search(result,data)
            summary={'id':result['id'],'status':result['status'],'queries':result['plan']['queries'],'input_hash':result['input_hash']}
            if result.get('review'):
                evidence.extend(validate_assessments(result,result['review'],data,root));summary['assessments']=result['review']['assessments'];summary['reviewer']=result['review']['reviewer'];summary['reviewed_at']=result['review']['reviewed_at']
            elif result['candidates']:summary['unreviewed_candidates']=[c['id'] for c in result['candidates']]
            reviews.append(summary)
        except (ValueError,KeyError,TypeError,OSError) as exc:issues.append('Counterevidence '+str(exc))
    return evidence,reviews,issues

def check_counterevidence(data,rep,root,release=False):
    indexed={};seen=set()
    for result in data.get('counterevidence_searches',[]):
        try:
            if result['id'] in seen:raise ValueError('Duplicate counter-search ID')
            seen.add(result['id']);validate_search(result,data)
            if result.get('review'):validate_assessments(result,result['review'],data,root)
            indexed.setdefault(result['plan']['target_id'],[]).append(result)
        except (ValueError,KeyError,TypeError,OSError) as exc:rep.err('counterevidence_searches',str(exc))
    endorsed={c['target_id'] for c in data.get('publication',{}).get('conclusions',[]) if c['disposition']=='endorsed'}
    required=endorsed|{p['id'] for p in data.get('proposals',[])}
    if release:
        for target_id in sorted(required):
            searches=indexed.get(target_id,[])
            if not searches:rep.err(target_id,'Missing active counterevidence search')
            if target_id in endorsed:
                if not any(r['status'] in ('searched','not_found') for r in searches):rep.err(target_id,'Endorsement needs a completed counter-search; failures do not establish absence of opposition')
                for result in searches:
                    review=result.get('review')
                    if result['candidates'] and (not review or any(a['classification']=='unresolved' for a in review['assessments'])):rep.err(target_id,'Review unresolved counterevidence before endorsement')
    return {'required':len(required),'accounted':len(required & set(indexed)),'status':'complete' if required<=set(indexed) else 'pending',
        'limit':'Bounded searches cannot prove that no counterevidence exists'}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command')
    p=sub.add_parser('search');p.add_argument('anatomy');p.add_argument('--plan',required=True);p.add_argument('--limit',type=int,default=3);p.add_argument('-o','--output',required=True)
    p=sub.add_parser('apply');p.add_argument('anatomy');p.add_argument('--search',required=True);p.add_argument('--review');p.add_argument('-o','--output',required=True)
    a=ap.parse_args(argv)
    if not a.command:ap.error('Choose search or apply')
    target=Path(a.output)
    if target.exists():ap.error('Choose a new output file')
    def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    try:
        data=load(a.anatomy)
        if a.command=='search':output=search(load(a.plan),data,a.limit)
        else:
            if target.resolve().parent!=Path(a.anatomy).resolve().parent:raise ValueError('Keep anatomy beside its evidence bundle')
            result=load(a.search);validate_search(result,data)
            if a.review:result['review']=load(a.review);validate_assessments(result,result['review'],data,Path(a.anatomy).resolve().parent)
            output=data;output['counterevidence_searches']=[r for r in data.get('counterevidence_searches',[]) if r['id']!=result['id']]+[result]
            blockers=data.get('stage',{}).get('blocking_items',[])
            output['stage']={'stage':'G8','stage_status':'blocked' if blockers else 'pending','blocking_items':blockers,'receipts':[]}
        target.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(str(target));return 0
    except (ValueError,KeyError,TypeError,OSError) as exc:ap.error(str(exc))
if __name__=='__main__':raise SystemExit(main())
