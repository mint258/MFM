"""Render the first complete noise-head result, preserving its partial scientific scope."""
import hashlib,json,os,socket,subprocess,time
from pathlib import Path
from stage3_gate_v4 import estimate_cost,query_parents
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
PYTHON='/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
def ref(path):
    raw=Path(path).read_bytes();return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
def main():
    assert os.getuid()==1278 and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-8','compute-0-9','compute-0-10','compute-0-11']
    began=time.monotonic();snapshot=ROOT/'control/accounting_snapshots/first_noise_report_v3.json'
    output=ROOT/'reports/D3_interim_A0_A1_A2_v3'
    p=subprocess.run([PYTHON,'-B',str(ROOT/'analysis/render_d3_report_v3.py'),'--phases','d3_report_projection_v3',
       '--parent-snapshot',str(snapshot),'--output-dir',str(output)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
    if p.returncode:print(p.stdout,p.stderr,flush=True)
    assert p.returncode==0
    pointer=json.loads((ROOT/'reports/A2_seed0_latest.json').read_text());assert ref(pointer['path'])['sha256']==pointer['sha256']
    result=json.loads(Path(pointer['path']).read_text());assert result['status']=='D3_CONDITION_COMPLETE' and result['runtime']['job_id']=='4515578'
    actual=query_parents({'4515578'},snapshot);curve=Path(pointer['path']).with_name('curve.json')
    estimator=ROOT/'configs/cost_estimator_v2.json'
    cost=estimate_cost(result,json.loads(curve.read_text()),int(actual['4515578'][2]),json.loads(estimator.read_text()))
    cost_doc={'status':'ONE_COMPLETE_LR_COST_PROFILE_NOT_FINAL_STAGE3_SELECTION','condition':'A2','seed':0,
      'cost':cost,'references':[ref(estimator),ref(curve),ref(pointer['path']),ref(snapshot)],
      'not_a_scientific_gate':True,'other_LRs_and_second_seed_pending':True,'formal_training_authorized':False}
    with (output/'A2_seed0_cost_profile.json').open('x') as f:json.dump(cost_doc,f,indent=2,allow_nan=False);f.write('\n')
    command=['pdftoppm','-f','1','-singlefile','-png','-scale-to','2000',str(output/'D3_curves.pdf'),str(output/'D3_curves_actual_pdf')]
    render=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
    assert render.returncode==0,render.stderr
    receipt={'status':'INTERIM_FIRST_COMPLETE_NOISE_HEAD_REPORT_REQUIRES_VISUAL_REVIEW','job_id':os.environ['SLURM_JOB_ID'],
      'elapsed_seconds':time.monotonic()-began,'plot_returncode':p.returncode,'pdf_render_returncode':render.returncode,
      'artifacts':[ref(output/name) for name in ['D3_curves.pdf','D3_curves_actual_pdf.png','D3_conditions.csv','D3_table.md','measurements.json','A2_seed0_cost_profile.json']],
      'scientific_gate_declared_passed':False,'source_references':[ref(Path(__file__)),ref(ROOT/'analysis/render_d3_report_v3.py'),ref(ROOT/'analysis/stage3_gate_v4.py')],
      'actual_baseline_closure_reference':ref(ROOT/'configs/lookup_refit_closure_v1.json')}
    with (output/'render_and_cost_receipt.json').open('x') as f:json.dump(receipt,f,indent=2,allow_nan=False);f.write('\n')
    print(receipt['status'],json.dumps(cost_doc['cost']),flush=True)
if __name__=='__main__':main()
