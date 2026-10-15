"""Bind the reviewed five-dataset probe generation to explicit CPU resources."""
import json,os,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha

def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    assert not (ROOT/'probe_preparation_control/production_binding_v1.json').exists()
    for job in ['4515117','4515114','4515118']:
        raw=subprocess.run(['sacct','-j',job,'-n','-P','--format=JobIDRaw,User,State,ExitCode'],capture_output=True,text=True,check=True,timeout=30).stdout
        rows=[r.split('|') for r in raw.splitlines() if r.split('|')[0]==job]
        assert len(rows)==1 and rows[0][1:]==['zixiao','COMPLETED','0:0']
    proof=json.loads((ROOT/'reports/s_linear_probe_integration_v1.json').read_text())
    assert proof['status']=='ACTUAL_H0_LINEAR_INTEGRATION_AND_HELDOUT_TARGET_INDEPENDENCE_PASS'
    assert proof['source_sha256']==sha(ROOT/'scripts/run_s_linear_probes_v1.py')
    review=[]
    for dataset in ['qm7','qm9','cyp_isoform','az_exactsom','expansionrx']:
        receipt_path=ROOT/'probe_data_development_v3'/(dataset+'_receipt.json');receipt=json.loads(receipt_path.read_text())
        assert receipt['job_id']=='4515117' and receipt['processed_members']==16
        assert receipt['geometry_status_counts']=={'GEOMETRY_READY':16}
        assert receipt['generator_sha256']==sha(ROOT/'scripts/prepare_s_probe_data_v3.py')
        review.append({'path':str(receipt_path),'sha256':sha(receipt_path)})
    assignments=[('qm7',8,32),('qm9',9,64),('cyp_isoform',10,32),('az_exactsom',11,32),('expansionrx',12,64)]
    scripts=[]
    for dataset,node,cpus in assignments:
        stem='s_probe_full_'+dataset+'_v3';path=ROOT/'scripts'/(stem+'.sbatch');assert not path.exists()
        lines=['#!/bin/bash','#SBATCH --job-name=sconv_'+stem,'#SBATCH --partition=cpu',
            '#SBATCH --nodelist=compute-0-'+str(node),'#SBATCH --cpus-per-task='+str(cpus),'#SBATCH --mem=64G','#SBATCH --time=24:00:00',
            '#SBATCH --output='+str(ROOT/'logs'/(stem+'_%j.log')),'set -euo pipefail','cd '+str(PROJECT),
            'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1',"export CUDA_VISIBLE_DEVICES=''",
            'export PYTHONPATH=/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime:'+str(PROJECT/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'),
            '/share/home/zixiao/.conda/envs/chemprop/bin/python -B '+str(ROOT/'scripts/prepare_s_probe_data_v3.py')+' --dataset '+dataset]
        path.write_text('\n'.join(lines)+'\n')
        scripts.append({'dataset':dataset,'path':str(path),'sha256':sha(path),'node':'compute-0-'+str(node),'cpus':cpus,'memory_gib':64})
    value={'status':'REVIEWED_PROBE_INPUT_PRODUCTION_BOUND_NOT_YET_SUBMITTED','timestamp':time.time(),'scripts':scripts,
        'generator':{'path':str(ROOT/'scripts/prepare_s_probe_data_v3.py'),'sha256':sha(ROOT/'scripts/prepare_s_probe_data_v3.py')},
        'smoke_receipts':review,'linear_probe_proof_sha256':sha(ROOT/'reports/s_linear_probe_integration_v1.json'),
        'guide_sha256':sha(ROOT/'configs/user_guide.md'),'checkpoint_model_parameters_changed':False,
        'disposition':'retain all declared members; malformed annotation stays unknown independently of UFF geometry',
        'population_membership_deleted':0,'original_sources_written':False,'new_lmdb_created':False}
    save(ROOT/'probe_preparation_control/production_binding_v1.json',value);print(json.dumps(value),flush=True)

if __name__=='__main__':main()
