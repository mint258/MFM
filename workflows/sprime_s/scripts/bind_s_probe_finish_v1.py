"""Seal tested probe code and the full generation receipts for Root monitoring."""
import json,os,time
from prepare import ROOT,save,sha

def main():
    assert os.getuid()==1278
    production=json.loads((ROOT/'probe_preparation_control/production_binding_v1.json').read_text())
    for item in production['scripts']:
        assert sha(item['path'])==item['sha256']
        from pathlib import Path
        receipt=ROOT/'submission'/(Path(item['path']).stem+'.json')
        value=json.loads(receipt.read_text());assert value['job_id'] and value['sbatch_rc']==0
    names=['prepare_s_probe_data_v3.py','validate_s_probe_inputs_v1.py','s_probe_overlap_v1.py',
        'extract_s_probe_h0_v2.py','run_s_linear_probes_v1.py','s_probe_finish_root_v1.py']
    refs=[{'path':str(ROOT/'scripts'/name),'sha256':sha(ROOT/'scripts'/name)} for name in names]
    path=ROOT/'probe_preparation_control/finish_binding_v1.json';assert not path.exists()
    save(path,{'status':'ROOT_BOUND_REVIEWED_PROBE_FINISH_FLOW','timestamp':time.time(),'sources':refs,
        'production_binding_sha256':sha(ROOT/'probe_preparation_control/production_binding_v1.json'),
        'real_H0_interface_proof_job':'4515114','linear_probe_integration_proof_job':'4515118',
        'guide_defined_endpoints_only':True,'no_development_checkpoint_is_a_formal_endpoint':True,
        'full_probe_results_closed':False})
    print('PROBE_FINISH_FLOW_BOUND_NOT_COMPLETED',flush=True)

if __name__=='__main__':main()
