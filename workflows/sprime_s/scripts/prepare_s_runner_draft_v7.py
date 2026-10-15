"""Bind a new tested runner version without selecting formal science here."""
import json
from pathlib import Path
from prepare import ROOT,save,sha

def main():
    value=json.loads((ROOT/'configs/s_runner_development_v6.json').read_text())
    assert value['status']=='DRAFT_CANDIDATE_INTERFACE_ONLY'
    assert value['frozen_reference_resolution']['resolved'] is False
    replaced=False
    for ref in value['source_references']:
        assert sha(ref['path'])==ref['sha256']
        if Path(ref['path']).name=='s_convergence_runner_v6.py':
            ref['path']=str(ROOT/'scripts/s_convergence_runner_v7.py')
            ref['sha256']=sha(ref['path']);ref['bytes']=Path(ref['path']).stat().st_size
            replaced=True
    assert replaced
    path=ROOT/'scripts/s_loader_recovery_v2.py'
    value['source_references'].append({'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size})
    target=ROOT/'configs/s_runner_development_v7.json';assert not target.exists()
    save(target,value);print('DRAFT_V7_NOT_FORMAL',flush=True)

if __name__=='__main__':main()
