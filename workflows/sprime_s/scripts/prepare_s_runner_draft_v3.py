"""Bind updated development entry and unchanged candidate settings; no selection."""
import json
from pathlib import Path
from prepare import ROOT,save,sha

def main():
    old=ROOT/'configs/s_runner_development_v2.json';value=json.loads(old.read_text())
    assert value['status']=='DRAFT_CANDIDATE_INTERFACE_ONLY' and value['frozen_reference_resolution']['resolved'] is False
    for ref in value['source_references']:
        assert sha(ref['path'])==ref['sha256']
        if Path(ref['path']).name=='s_convergence_runner_v2.py':
            ref['path']=str(ROOT/'scripts/s_convergence_runner_v3.py');ref['sha256']=sha(ref['path']);ref['bytes']=Path(ref['path']).stat().st_size
    target=ROOT/'configs/s_runner_development_v3.json';assert not target.exists()
    save(target,value);print('DEVELOPMENT_CONFIGURATION_V3_ONLY',flush=True)

if __name__=='__main__':main()
