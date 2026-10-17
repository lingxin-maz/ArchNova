# -*- coding: utf-8 -*-
"""Publish complete honest findings without promoting unresolved claims."""
def check_publication(data,states,rep,release=False):
    policy=data.get('publication',{});mode=policy.get('mode','honest_report');seen=set()
    if mode not in ('honest_report','supported_conclusions'):rep.err('publication','Unknown publication mode')
    for conclusion in policy.get('conclusions',[]):
        key=(conclusion['kind'],conclusion['target_id']);disposition=conclusion['disposition']
        if key in seen or key not in states:rep.err('publication','Duplicate or unknown conclusion: '+str(key));continue
        seen.add(key);state=states[key]
        if disposition=='endorsed' and state!='supported':rep.err(key[1],'Cannot endorse unresolved/negative conclusion: '+state)
        if disposition=='rejected' and state!='contradicted':rep.err(key[1],'Rejected mathematical/factual claim needs a contradiction; otherwise report open')
        if disposition=='conditional' and not conclusion.get('conditions'):rep.err(key[1],'Conditional conclusion needs explicit conditions')
        if release and state=='not_reviewed':rep.err(key[1],'Prepare and review even missing-material tasks; do not silently omit them')
        if release and mode=='supported_conclusions' and (disposition!='endorsed' or state!='supported'):
            rep.err(key[1],'supported_conclusions mode requires all conclusions endorsed and supported')
    if release:
        for key in set(states)-seen:rep.err(key[1],'Missing explicit publication disposition')
    return {'mode':mode,'conclusions':len(seen),'required':len(states),'status':'complete' if len(seen)==len(states) else 'draft'}
