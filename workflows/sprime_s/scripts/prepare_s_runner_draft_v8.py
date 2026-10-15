"""Declare a runtime-only IPC wait extension after measured cold-start failure."""
import json
from pathlib import Path
from prepare import ROOT,save,sha

def main():
    value=json.loads((ROOT/'configs/s_runner_development_v7.json').read_text())
    assert value['status']=='DRAFT_CANDIDATE_INTERFACE_ONLY'
    assert value['frozen_reference_resolution']['resolved'] is False
    replaced=False
    for ref in value['source_references']:
        assert sha(ref['path'])==ref['sha256']
        if Path(ref['path']).name=='s_convergence_runner_v7.py':
            ref['path']=str(ROOT/'scripts/s_convergence_runner_v8.py')
            ref['sha256']=sha(ref['path']);ref['bytes']=Path(ref['path']).stat().st_size;replaced=True
    assert replaced and value['loader']['worker_timeout_seconds']==60.
    failure=ROOT/'development_s_runner/B1_seed0/segment_4515087_uninterrupted/summary.json'
    actual=json.loads(failure.read_text())
    assert actual['status']=='RUNNER_FAILED_RETRYABLE_LOADER_TIMEOUT' and actual['consumed_records']==0
    override={'parameter':'worker_timeout_seconds','frozen_reference_value':60.,'effective_value':600.,
        'scope':'IPC waiting guard only; identical workers, order, views, labels, batch budgets, model, optimizer and schedule',
        'basis':'Actual job4515087 exhausted three restarts before its first committed record; repeated60s startup reset prevented completion',
        'failure_evidence':{'path':str(failure),'sha256':sha(failure)}}
    value['loader']['worker_timeout_seconds']=600.
    value['runtime_loader_timeout_override']=override
    target=ROOT/'configs/s_runner_development_v8.json';assert not target.exists()
    save(target,value);print('DRAFT_V8_RUNTIME_WAIT_ONLY_NOT_FORMAL',flush=True)

if __name__=='__main__':main()
