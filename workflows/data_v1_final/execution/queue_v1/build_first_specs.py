"""Translate reviewed stage metadata into exact first-phase queue specs."""
from .shared import ROOT,REPO,PY,load,need,on_login,pin,write_new

def unique(refs):
    result={}
    for r in refs:
        p={k:r[k] for k in ('path','bytes','sha256')}
        need(p['path'] not in result or result[p['path']]==p,'CONFLICTING_REF')
        result[p['path']]=p
    return list(result.values())

def main():
    on_login();control=ROOT/'control/requests'
    dpath=control/'dv1_q_sprime_recovery_20261026_v1.dispatch.json';d=load(dpath)
    fmeta=load(ROOT/'control/pprime_frame_queue_materialized_20261026_v1.json');fpath=control/'dv1_q_pprime_frame_20261026_v1.plan.json';f=load(fpath)
    need(d['request_fields']['wall_seconds']==6900 and d['request_fields']['memory_gib']==64,'APPROVED_RECOVERY_SCOPE')
    need(f['wall_seconds']==7200 and f['memory_gib']==64 and f['expected_calls']==72,'APPROVED_FRAME_SCOPE')
    tests={'schema':'ROOT_REVIEWED_QUEUED_STAGE_SPEC_V1','kind':'analysis','pilot':True,'wall_seconds':600,
        'estimated_peak_output_bytes':96*1024**2,'execution_argv':[PY,'-B','-m','workflows.data_v1_final.execution.queue_v1.run_checks'],
        'source_references':unique([*d['source_references'],pin(dpath)]),'data_references':[],
        'scope':'New queue contract boundaries and six new recovery metadata fixtures only. Zero scientific calls/corpus reads.'}
    recovery={'schema':'ROOT_REVIEWED_QUEUED_STAGE_SPEC_V1','kind':'conformer','pilot':True,'wall_seconds':6900,
        'estimated_peak_output_bytes':d['request_fields']['estimated_peak_output_bytes'],'execution_argv':d['execution_argv'],
        'source_references':unique([*d['source_references'],pin(dpath)]),'data_references':unique(d['data_references']),
        'scope':'Only two missing original tasks plus14same-seed controls; preserve334oldpackages and original TIMEOUT. Original96corehour guide gate unchanged.'}
    frame={'schema':'ROOT_REVIEWED_QUEUED_STAGE_SPEC_V1','kind':'qm','pilot':True,'wall_seconds':7200,
        'estimated_peak_output_bytes':f['estimated_peak_output_bytes'],'execution_argv':fmeta['command_argv'],
        'source_references':unique([*f['source_references'],pin(fpath)]),'data_references':unique(f['data_references']),
        'scope':'72isolated real frame controls then original evaluator, not2000pilot or full frame certification.'}
    for name,obj in [('dv1_q_checks_20261026_v1',tests),('dv1_q_sprime_recovery_20261026_v1',recovery),('dv1_q_pprime_frame_20261026_v1',frame)]:
        p=control/(name+'.stage_spec.json');write_new(p,obj);print(__import__('json').dumps({'stage_spec':pin(p),'sources':len(obj['source_references']),'data_locators':len(obj['data_references'])}))
if __name__=='__main__':main()
