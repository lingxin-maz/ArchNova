# -*- coding: utf-8 -*-
"""Fetch and validate operator metadata without executing remote code."""
import argparse,hashlib,json,urllib.request,urllib.error
from pathlib import Path
from orchestrator import atomic_write,digest
MAX_BYTES=512*1024
REQUIRED={'schema_version','operator_id','version','kind','license','source','implementation','verification'}
BUILTIN={'identity','scale','relu','tanh','linear','add','matmul','transpose','softmax','reshape','concat','layernorm'}
def validate_record(record):
 if not isinstance(record,dict) or not REQUIRED<=set(record): raise ValueError('Operator record is incomplete')
 if not isinstance(record['operator_id'],str) or not record['operator_id'] or record['operator_id'] in BUILTIN: raise ValueError('Invalid or builtin operator_id')
 if not isinstance(record['version'],str) or not record['license']: raise ValueError('Operator version/license required')
 if record['kind'] not in ('elementwise','reduction','layout','linear','attention','convolution','recurrent','custom'): raise ValueError('Unknown operator kind')
 source=record['source']
 if not isinstance(source,dict) or not source.get('url','').startswith('https://') or not isinstance(source.get('sha256'),str) or len(source['sha256'])!=64: raise ValueError('Operator source must be HTTPS with SHA-256')
 impl=record['implementation']
 if not isinstance(impl,dict) or impl.get('language') not in ('python','torch','jax','declarative') or not impl.get('entry'): raise ValueError('Implementation entry required')
 verification=record['verification']
 if not isinstance(verification,dict) or verification.get('status') not in ('unverified','reviewed','verified'): raise ValueError('Invalid verification status')
 return record
def fetch_record(url,expected_sha256=None,timeout=15):
 if not str(url).startswith('https://'): raise ValueError('Only HTTPS operator sources are allowed')
 req=urllib.request.Request(url,headers={'User-Agent':'arch-anatomy-operator-registry/1.0'})
 with urllib.request.urlopen(req,timeout=timeout) as response: body=response.read(MAX_BYTES+1)
 if len(body)>MAX_BYTES: raise ValueError('Operator record exceeds size limit')
 actual=hashlib.sha256(body).hexdigest()
 if expected_sha256 and actual!=expected_sha256: raise ValueError('Operator record SHA-256 mismatch')
 record=json.loads(body.decode('utf8'));validate_record(record);record=dict(record);record['retrieval']={'url':url,'sha256':actual,'retrieved_by':'arch-anatomy'};return record
def save_record(record,path):
 validate_record(record);atomic_write(path,record);return {'path':str(path),'sha256':digest(record),'status':record['verification']['status']}
def activate_record(record,local_implementation=False):
 validate_record(record)
 if record['verification']['status'] not in ('reviewed','verified'): return {'status':'blocked','reason':'Operator metadata is not reviewed','operator_id':record['operator_id']}
 if not local_implementation:return {'status':'blocked','reason':'No local reviewed implementation is registered','operator_id':record['operator_id']}
 return {'status':'available','operator_id':record['operator_id'],'version':record['version']}
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='cmd',required=True);f=sub.add_parser('fetch');f.add_argument('--url',required=True);f.add_argument('--sha256');f.add_argument('-o','--output',required=True);v=sub.add_parser('validate');v.add_argument('record');a=p.parse_args()
 try:
  if a.cmd=='fetch': print(json.dumps(save_record(fetch_record(a.url,a.sha256),a.output),ensure_ascii=False))
  else: validate_record(json.loads(Path(a.record).read_text(encoding='utf8')));print(json.dumps({'status':'valid'}))
 except (ValueError,OSError,KeyError,urllib.error.URLError) as exc:p.error(str(exc))
if __name__=='__main__':main()
