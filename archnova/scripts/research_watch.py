# -*- coding: utf-8 -*-
"""Live research watcher for neural-network system architecture evidence."""
import argparse,datetime,hashlib,json,urllib.parse,urllib.request,urllib.error
from pathlib import Path
from orchestrator import atomic_write,digest
TEAMS={'openai':['OpenAI'],'deepmind':['Google DeepMind','DeepMind'],'meta_fair':['Meta AI','Facebook AI Research'],'microsoft':['Microsoft Research'],'nvidia':['NVIDIA Research'],'anthropic':['Anthropic'],'berkeley':['University of California, Berkeley'],'stanford':['Stanford University']}
TAGS={'kv_cache':['kv cache','paged attention','key-value cache','inference memory'],'optimizer_state':['optimizer state','adam','zero','fsdp','sharding'],'mixture_of_experts':['mixture of experts','moe','router','expert'],'tokenizer':['tokenizer','bpe','sentencepiece'],'tensor_parallel':['tensor parallel','sequence parallel','expert parallel'],'pipeline_parallel':['pipeline parallel','pipeline bubbles'],'spectral_or_kernel_operator':['neural operator','fourier neural operator','spectral convolution'],'message_passing':['graph neural','message passing','graph transformer'],'noise_schedule':['diffusion','score model','noise schedule'],'state_space':['state space model','selective scan','ssm'],'cross_attention':['multimodal','cross-attention','vision-language'],'normalization':['rmsnorm','layernorm','normalization']}
def _get(url,timeout=20):
 req=urllib.request.Request(url,headers={'User-Agent':'archnova-research-watch/1.0'})
 with urllib.request.urlopen(req,timeout=timeout) as r:
  body=r.read(4*1024*1024+1)
 if len(body)>4*1024*1024: raise ValueError('Research response exceeds budget')
 return json.loads(body.decode('utf8')),hashlib.sha256(body).hexdigest()
def _date(days): return (datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=days)).date().isoformat()
def _abstract(inv):
 if not isinstance(inv,dict):return ''
 return ' '.join(word for _,word in sorted((pos,w) for w,poses in inv.items() for pos in poses))
def _norm(work,team,query):
 authors=[]
 for a in work.get('authorships') or []:
  author=a.get('author') or {};inst=[i.get('display_name') for i in a.get('institutions') or []]
  authors.append({'name':author.get('display_name'),'institutions':inst})
 text=((work.get('title') or '')+' '+_abstract(work.get('abstract_inverted_index'))).casefold()
 tags=[tag for tag,terms in TAGS.items() if any(term in text for term in terms)]
 return {'id':work.get('id'),'title':work.get('title'),'publication_date':work.get('publication_date'),'doi':work.get('doi'),'url':work.get('doi') or work.get('id'),'team':team,'query':query,'authors':authors,'abstract':_abstract(work.get('abstract_inverted_index')),'architecture_tags':tags,'evidence_status':'candidate_requires_ai_review'}
def watch(teams=None,queries=None,since_days=30,limit=10):
 teams=teams or [];queries=queries or []
 if not teams and not queries: teams=['openai','deepmind','meta_fair','microsoft','nvidia']
 items=[];receipts=[];seen=set();since=_date(since_days)
 for team in teams:
  if team not in TEAMS: raise ValueError('Unknown team: '+team)
  for q in TEAMS[team]: queries.append(q+' neural network architecture')
 for query in queries[:12]:
  url='https://api.openalex.org/works?search='+urllib.parse.quote(query)+'&filter=from_publication_date:'+since+'&per-page='+str(min(max(limit,1),25))+'&select=id,title,publication_date,doi,authorships,abstract_inverted_index'
  body,sha=_get(url);receipts.append({'endpoint':url,'response_sha256':sha,'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
  for work in body.get('results',[]):
   key=work.get('id') or work.get('doi') or work.get('title')
   if key in seen:continue
   seen.add(key);items.append(_norm(work,teams[0] if teams else 'query',query))
 return {'schema_version':'1.0','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'since':since,'results':items[:max(1,limit*len(queries))],'receipts':receipts,'ai_extraction_contract':{'required_fields':['system_family','network_body','inference_state','training_state','preprocess','distributed_view','evidence_spans','uncertainties'],'status':'pending_host_ai_review'},'scope_limits':['OpenAlex discovery is a candidate feed, not a complete literature index.','Keyword tags are retrieval hints; architecture facts require paper/code evidence and host AI review.']}
def ai_prompt(record):
 return {'system':'Extract a generic neural-network system architecture ontology from the supplied paper metadata. Return JSON only; separate paper facts, code observations, derived claims, proposed designs, and unknowns. Never infer missing KV cache, optimizer state or parallelism.', 'input':record,'schema':['system_family','network_body','inference_state','training_state','preprocess','distributed_view','evidence_spans','uncertainties']}
def main():
 p=argparse.ArgumentParser();p.add_argument('--team',action='append',choices=sorted(TEAMS));p.add_argument('--query',action='append');p.add_argument('--since-days',type=int,default=30);p.add_argument('--limit',type=int,default=10);p.add_argument('-o','--output',required=True);a=p.parse_args();
 try:atomic_write(a.output,watch(a.team,a.query,a.since_days,a.limit));print(json.dumps({'status':'completed','output':a.output}))
 except (ValueError,OSError,urllib.error.URLError) as exc:p.error(str(exc))
if __name__=='__main__':main()

