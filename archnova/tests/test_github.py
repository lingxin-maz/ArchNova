# -*- coding: utf-8 -*-
import base64
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from unittest.mock import patch

class GithubTests(unittest.TestCase):
    def repo(self):
        return {'full_name':'owner/model','html_url':'https://github.com/owner/model','description':'A model implementation',
          'stargazers_count':100,'language':'Python','license':{'spdx_id':'MIT'},'archived':False,'default_branch':'main'}
    def test_readme_paper_id_is_relevance_not_official_status(self):
        from github_repos import assess_repository
        result=assess_repository(self.repo(),'Paper https://arxiv.org/abs/2312.00752',paper_id='2312.00752')
        self.assertEqual(result['relation'],'paper_id_in_readme')
        self.assertEqual(result['official_status'],'unconfirmed')
    def test_paper_linked_repo_is_distinguished(self):
        from github_repos import assess_repository
        result=assess_repository(self.repo(),'README',paper_text='Code: https://github.com/owner/model.')
        self.assertEqual(result['relation'],'paper_linked')
        self.assertEqual(result['official_status'],'unconfirmed')
    def test_similar_identifier_is_not_a_match(self):
        from github_repos import assess_repository
        result=assess_repository(self.repo(),'arxiv:2312.007520',paper_id='2312.00752')
        self.assertEqual(result['relation'],'keyword_candidate')
    def test_readme_base64_decode_and_hash(self):
        from github_repos import decode_readme
        result=decode_readme({'encoding':'base64','content':base64.b64encode(b'hello').decode(),'sha':'a'*40})
        self.assertEqual(result['text'],'hello');self.assertEqual(len(result['sha256']),64)
    def test_search_handles_rate_limit_without_fabricating_results(self):
        import github_repos
        with patch.object(github_repos,'get_json',return_value={'ok':False,'error':'HTTP 403','status':403}):
            result=github_repos.discover(title='Example paper',limit=2)
        self.assertEqual(result['status'],'unavailable');self.assertEqual(result['candidates'],[])
    def test_search_fetches_readme_and_preserves_receipt(self):
        import github_repos
        repo=self.repo()
        def transport(url):
            if '/search/repositories?' in url:return {'ok':True,'data':{'items':[repo],'incomplete_results':False},'receipt':{'endpoint':url}}
            return {'ok':True,'data':{'encoding':'base64','content':base64.b64encode(b'arxiv:2312.00752').decode(),'sha':'a'*40},'receipt':{'endpoint':url}}
        with patch.object(github_repos,'get_json',side_effect=transport):result=github_repos.discover(paper_id='2312.00752',limit=1)
        self.assertEqual(result['status'],'ok');self.assertEqual(result['candidates'][0]['relation'],'paper_id_in_readme')
        self.assertTrue(result['queries'])

    def test_judgment_plan_drives_queries_and_pinned_source_inspection(self):
        import github_repos
        plan={'target_id':'proposal:scan','judgment':'Dense mixing is costly',
              'mechanism':'associative prefix scan','required_features':['scan'],
              'interface_constraints':['causal sequence input'],
              'queries':['associative scan pytorch'],'code_hints':['scan']}
        calls=[]
        def transport(url):
            calls.append(url)
            if '/search/repositories?' in url:return {'ok':True,'data':{'items':[self.repo()]}}
            if '/commits/' in url:return {'ok':True,'data':{'sha':'a'*40,'commit':{'tree':{'sha':'b'*40}}}}
            if '/git/trees/' in url:return {'ok':True,'data':{'tree':[{'path':'src/scan.py','type':'blob','size':80}],'truncated':False}}
            text=b'def scan(x):\n    return x.cumsum(0)\n'
            return {'ok':True,'data':{'encoding':'base64','content':base64.b64encode(text).decode(),'sha':'c'*40}}
        with patch.object(github_repos,'get_json',side_effect=transport):
            result=github_repos.discover(title='Unrelated paper',plan=plan,limit=1,max_code_files=1)
        self.assertEqual(len(result['queries']),1)
        self.assertEqual(result['queries'][0]['query'],'associative scan pytorch')
        candidate=result['candidates'][0]
        self.assertEqual(candidate['source_inspection']['commit_sha'],'a'*40)
        self.assertEqual(candidate['source_inspection']['files'][0]['path'],'src/scan.py')
        self.assertTrue(any('ref='+('a'*40) in u for u in calls))
        self.assertEqual(candidate['implementation_review']['status'],'pending_host_review')
        self.assertEqual(candidate['implementation_review']['target_id'],'proposal:scan')

    def test_plan_requires_actual_judgment_and_features(self):
        import github_repos
        with self.assertRaises(ValueError):github_repos.discover(plan={'queries':['attention']})

    def test_unavailable_code_never_establishes_implementation_fit(self):
        import github_repos
        with patch.object(github_repos,'get_json',return_value={'ok':False,'error':'HTTP 403','status':403}):
            result=github_repos.inspect_repository(self.repo(),{'code_hints':['scan']},1)
        self.assertEqual(result['status'],'unavailable')
        self.assertEqual(result['files'],[])

    def test_fit_review_requires_real_source_line_evidence(self):
        import github_repos
        plan={'target_id':'proposal:scan','judgment':'Cost bottleneck','mechanism':'scan',
              'required_features':['scan'],'interface_constraints':['causal'],'queries':['scan'],'code_hints':['scan']}
        inspection={'commit_sha':'a'*40,'status':'inspected','files':[{'path':'scan.py','text':'def scan(x):\n    return x.cumsum(0)\n'}]}
        candidate={'full_name':'owner/model','source_inspection':inspection,
                   'implementation_review':github_repos.implementation_task(plan,inspection)}
        review={'full_name':'owner/model','input_hash':candidate['implementation_review']['input_hash'],
                'fit':'adaptable','rationale':'Cumulative sums need an associative operator extension',
                'feature_checks':[{'requirement':'scan','status':'satisfied','evidence':[{'commit':'a'*40,'path':'scan.py','start_line':1,'end_line':2,'explanation':'Cumulative sum'}]}],
                'interface_checks':[{'requirement':'causal','status':'satisfied','evidence':[{'commit':'a'*40,'path':'scan.py','start_line':2,'end_line':2,'explanation':'No future indices'}]}],
                'integration_changes':['Generalize sum to operator composition'],'limitations':['Not executed'],
                'minimal_test':'Compare to sequential recurrence',
                'reviewer':{'identity':'test host','model':'test'},'reviewed_at':'2026-10-17T00:00:00Z'}
        github_repos.validate_fit_review(candidate,review)
        review['feature_checks'][0]['evidence'][0]['end_line']=999
        with self.assertRaises(ValueError):github_repos.validate_fit_review(candidate,review)
        review['feature_checks'][0]['evidence'][0]['end_line']=2
        review['input_hash']='b'*64
        with self.assertRaises(ValueError):github_repos.validate_fit_review(candidate,review)

    def test_repository_judgment_is_invalidated_by_proposal_change(self):
        import github_repos
        plan={'target_id':'proposal:scan','judgment':'Cost bottleneck','mechanism':'scan',
              'required_features':['scan'],'interface_constraints':['causal'],'queries':['scan'],'code_hints':['scan']}
        data={'proposals':[{'id':'proposal:scan','mechanism':'associative recurrence'}],'parts':[],
              'interface_contract':{'input_object':'sequence'},'dataflow':{}}
        bound=github_repos.bind_plan(plan,data)
        data['proposals'][0]['mechanism']='non-associative recurrence'
        self.assertNotEqual(bound['target_snapshot_hash'],github_repos.bind_plan(plan,data)['target_snapshot_hash'])

if __name__=='__main__':unittest.main()
