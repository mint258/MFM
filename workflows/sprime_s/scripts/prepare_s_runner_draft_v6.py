"""Bind bounded loader recovery for the still-unselected candidate protocol."""
import json
from pathlib import Path
from prepare import ROOT,save,sha

def main():
    value=json.loads((ROOT/'configs/s_runner_development_v5.json').read_text())
    assert value['status']=='DRAFT_CANDIDATE_INTERFACE_ONLY'
    assert value['frozen_reference_resolution']['resolved'] is False
    replaced=False
    for ref in value['source_references']:
        assert sha(ref['path'])==ref['sha256']
        if Path(ref['path']).name=='s_convergence_runner_v5.py':
            ref['path']=str(ROOT/'scripts/s_convergence_runner_v6.py')
            ref['sha256']=sha(ref['path']);ref['bytes']=Path(ref['path']).stat().st_size
            replaced=True
    assert replaced
    path=ROOT/'scripts/s_loader_recovery_v1.py'
    value['source_references'].append({'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size})
    value['runtime_loader_recovery']={'max_restarts_per_iterator':3,
        'trigger':'exact PyTorch DataLoader timeout only',
        'frozen_worker_timeout_seconds_unchanged':value['loader']['worker_timeout_seconds'],
        'cursor':'committed sampler state; drop uncommitted prefetch',
        'parent_cpu_rng':'preserve across retry worker creation',
        'exhaustion':'FAILED; save committed checkpoint for explicit continuation'}
    target=ROOT/'configs/s_runner_development_v6.json';assert not target.exists()
    save(target,value);print('DRAFT_V6_NOT_FORMAL',flush=True)

if __name__=='__main__':main()
