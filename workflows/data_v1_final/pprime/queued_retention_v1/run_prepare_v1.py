"""Execute the unchanged retention preparation body after strict CPU64G admission."""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,socket,subprocess,sys,time,traceback
HERE=pathlib.Path(__file__).absolute().parent
sys.path.insert(0,str(HERE))
from binding_v1 import need,prove_runtime_copy,validate_start,validate_closed
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
PROJECT=ROOT.parent.parent;PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'

def ref(path):
    path=pathlib.Path(path);h=hashlib.sha256()
    with path.open('rb') as f:
        a=os.fstat(f.fileno())
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
        b=os.fstat(f.fileno())
    need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'INPUT_CHANGED_DURING_READ')
    return {'path':str(path),'bytes':a.st_size,'sha256':h.hexdigest()}

def check(pin):
    actual=ref(pin['path']);need(all(actual[k]==pin[k] for k in ('path','sha256')) and ('bytes' not in pin or actual['bytes']==pin['bytes']),'CLOSED_SOURCE_OR_OUTPUT_PIN_CHANGED')
    return pathlib.Path(pin['path'])

def load(path):return json.loads(pathlib.Path(path).read_text())

def write_new(path,obj):
    with pathlib.Path(path).open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--root-preflight',type=pathlib.Path,required=True);a=p.parse_args()
    plan=load(a.plan);proof=load(a.root_preflight);node=socket.gethostname().split('.')[0]
    validate_start(plan,proof,dict(os.environ),node,os.getuid(),time.time())
    sources={pin['path']:pin for pin in proof['request']['source_references']}
    for path in (a.plan,pathlib.Path(__file__).absolute()):need(sources.get(str(path))==ref(path),'CURRENT_PLAN_WRAPPER_NOT_ROOT_PINNED')
    need(str(a.root_preflight)==plan['execution_intent_path'],'EXACT_EXECUTION_PROOF_PATH_REQUIRED')
    for pin in plan['source_references']:need(sources.get(pin['path'])==pin,'REVIEWED_SOURCE_NOT_IN_EXECUTION_REQUEST');check(pin)
    proof_file=load(check(plan['source_proof']))
    need(proof_file['variant_source']==plan['core_variant'] and proof_file['original_source']==plan['original_source'],'EXACT_SOURCE_EQUIVALENCE_BINDING_REQUIRED')
    comparison=prove_runtime_copy(check(plan['original_source']).read_bytes(),check(plan['core_variant']).read_bytes())
    prefix=pathlib.Path(plan['output_prefix']);out=pathlib.Path(plan['retention_output'])
    need(prefix.parent==ROOT/'artifacts/pprime_retention_v1' and out==prefix/'prepared' and not prefix.exists(),'NEW_RETENTION_OUTPUT_ONLY_NO_RETRY')
    prefix.mkdir(mode=0o700)
    write_new(prefix/'queue_start.json',{'status':'RETENTION_PREPARATION_STARTED_NOT_QM','job_id':os.environ['SLURM_JOB_ID'],
        'plan':ref(a.plan),'root_preflight':ref(a.root_preflight),'new_UFF_QM_calls':0})
    original=pathlib.Path(plan['original_prepared']['path'])
    command=[PY,'-B',plan['core_variant']['path'],'--config',plan['config']['path'],
        '--original-prepared',str(original.parent),'--original-prepared-sha256',plan['original_prepared']['sha256'],
        '--root-preflight',str(a.root_preflight),'--output',str(out)]
    code=None;error=None;counts=None;manifest_ref=None;outputs=[]
    try:
        code=subprocess.run(command,cwd=PROJECT,stdin=subprocess.DEVNULL).returncode
        manifest_path=out/'retention_manifest.json'
        if code==0 and manifest_path.is_file():
            manifest=load(manifest_path);manifest_ref=ref(manifest_path)
            required=('original_prepared','original_pairs','original_audit_membership','original_audit_selected20','source_plan',
                'source_audit','stable_full_hits','pilot_retention_union','engine_record_audit_membership','engine_selected','audit_policy')
            for key in required:outputs.append(ref(check(manifest[key])))
            import pyarrow.parquet as pq
            source_rows=load(manifest['source_audit']['path']);union_rows=load(manifest['pilot_retention_union']['path'])
            stable_rows=load(manifest['stable_full_hits']['path'])
            engine_rows=pq.read_table(manifest['engine_selected']['path']).to_pylist()
            original20=pq.read_table(manifest['original_audit_selected20']['path']).to_pylist()
            counts=validate_closed(manifest,source_rows,union_rows,stable_rows,engine_rows,[r['record_id'] for r in original20],plan)
            check(plan['original_pairs']);check(plan['original_prepared']);check(plan['config'])
    except Exception as exc:error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    accepted=code==0 and error is None and counts is not None
    result={'schema':'PPRIME_QUEUED_RETENTION_PREPARATION_ACTUAL_V1',
        'status':'ACTUAL_RETENTION_PREPARATION_COMPLETE_NOT_QM_AUTHORITY' if accepted else 'RETENTION_PREPARATION_NOT_ACCEPTED_REPORT_ROOT',
        'job_id':os.environ['SLURM_JOB_ID'],'node':node,'plan':ref(a.plan),'root_preflight':ref(a.root_preflight),
        'command_argv':command,'working_directory':str(PROJECT),'prepare_returncode':code,'error':error,
        'retention_manifest':manifest_ref,'actual_counts':counts,'verified_input_and_output_references':outputs,'source_equivalence':comparison,
        'source_original_pairs_and_policy_unchanged':accepted,'new_UFF_QM_calls':0,'original_sprime_or_uff_regenerated':False,
        'original_inputs_or_outputs_modified':False,'frame_acceptance_claimed':False,'full_or2000_QM_release':False,
        'signals_sent':False,'automatic_retry':False,
        'cost_basis':'Root actual sacct parent only, including failures; keep preparation and future2000QM accounting together for aggregate pipeline costs.'}
    write_new(plan['queue_receipt_output'],result)
    print(json.dumps({'status':result['status'],'receipt':ref(plan['queue_receipt_output']),'retention_manifest':manifest_ref,'actual_counts':counts,'new_UFF_QM_calls':0}))
    return 0 if accepted else 3
if __name__=='__main__':sys.exit(main())
