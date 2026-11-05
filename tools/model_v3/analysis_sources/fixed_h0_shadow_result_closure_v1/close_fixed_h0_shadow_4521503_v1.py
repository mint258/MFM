"""Independent Root metadata closure for CPU shadow1503; no tensor/SDK/model read."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import time
sys.dont_write_bytecode=True

P=Path('/share/home/zixiao/descriptor_analysis');N=P/'runs/model_v3_20261026';O=P/'runs/model_v3_20261025'
OUTPUT=O/'fixed_h0_shadow_cpu_v3_4521503';SOURCE=N/'numeric_fixed_h0_shadow_v3_source'
PIN='2fc31c55ccd916778730f5d047cf4a9018e81ab95c528dee8e173dd2225ee6fc'
FORBIDDEN={'.npz','.npy','.pt','.pth','.wandb','.safetensors','.lmdb','.mdb','.pkl','.pickle','.parquet'}


def require(value,message):
    if not value:raise ValueError(message)


def ref(path):
    path=Path(path).absolute();require(path.suffix.lower() not in FORBIDDEN,'Payload access prohibited')
    before=path.lstat();require(path==path.resolve(strict=True) and stat.S_ISREG(before.st_mode)
        and before.st_uid==os.getuid() and before.st_nlink==1 and before.st_size<=16<<20,'Owned bounded metadata/source required')
    raw=path.read_bytes();after=path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Metadata changed during binding')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read(path):
    before=ref(path)
    def pairs(items):
        value={}
        for key,item in items:require(key not in value,'Duplicate metadata JSON key');value[key]=item
        return value
    value=json.loads(Path(path).read_bytes(),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON literal')))
    require(ref(path)==before,'Metadata changed during parsing');return value


def bound(value):
    require(set(value)=={'path','bytes','sha256'} and ref(value['path'])==value,'Raw metadata/source reference differs')
    return read(value['path'])


def write(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    require(len(raw)<=2<<20,'Compact closure metadata only')
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return ref(path)


def numbers(value):
    if type(value) is list:
        return [number for child in value for number in numbers(child)]
    require(type(value) in (int,float) and math.isfinite(value),'Finite saved scalar required')
    return [float(value)]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=N/'fixed_h0_shadow_4521503_Root_closure_v1.json')
    parser.add_argument('--accounting-output',type=Path,default=N/'fixed_h0_shadow_4521503_raw_accounting_v1.json')
    args=parser.parse_args()
    require(os.getuid()==1278 and socket.gethostname()=='sonmi' and os.environ.get('CUDA_VISIBLE_DEVICES')=='',
        'Actual Root login metadata identity with hidden CUDA required')
    require(all(path.absolute().parent==N and not path.exists() for path in (args.output,args.accounting_output)),
        'Fresh immediate N closure/accounting paths required')
    pins_ref=ref(SOURCE/'source_pins_v1.json');require(pins_ref['sha256']==PIN,'Exact CPU v3 source pins differ')
    pins=bound(pins_ref);complete_ref=ref(OUTPUT/'COMPLETE.json');complete=bound(complete_ref)
    require(complete['schema']=='model_v3_fixed_h0_terminal_shadow_complete_v1' and complete['sources_unchanged'] is True,
        'Actual shadow COMPLETE/source closure required')
    result=bound(complete['result']);require(Path(complete['result']['path'])==OUTPUT/'SHADOW_RESULT.json'
        and result['schema']=='model_v3_fixed_h0_terminal_shadow_result_v1' and result['status']=='SHADOW_COMPLETE'
        and result['lineage']=='fresh_capture_not_1435_H0' and result['CPU_analysis_source_pins']==pins_ref
        and result['physical_FP32_threshold_changed'] is False and result['scientific_adoption'] is False,
        'Actual shadow result/scope/source differs')
    require(pins['role']=='CPU_SHADOW_METADATA_ADAPTER_ONLY_NOT_CAPTURE_PRODUCER'
        and pins['operational_revision']==3 and result['capture_producer_source_pins']==pins['capture_producer_source_pins'],
        'CPU adapter must retain original capture producer identity')
    capture_complete=bound(result['capture_complete']);capture=bound(capture_complete['manifest']);request=bound(capture['request'])
    require(capture_complete['schema']=='model_v3_fixed_h0_capture_complete_v1'
        and capture['status']=='CAPTURE_COMPLETE' and capture['failure'] is None
        and capture['job_id']=='4521492' and capture['source_before_after_equal'] is True
        and len(capture['cases'])==48 and capture['encoder_forwards']==capture['completed_case_encoder_forwards']==192,
        'Bound actual closed48-case capture1492 metadata required')
    before_ref=ref(OUTPUT/'sources_before.json');after_ref=ref(OUTPUT/'sources_after.json')
    before=bound(before_ref);after=bound(after_ref);require(before==after,'Full source before/after maps differ')
    expected={}
    for leaf in request['source_refs']+pins['files']+pins['protected_dependencies']+[pins_ref]:
        require(leaf['path'] not in expected or expected[leaf['path']]==leaf,'Conflicting expected source reference')
        expected[leaf['path']]=leaf
    require(before==expected,'Full source snapshot missing/extra/changed entry')
    for path,value in before.items():require(path==value['path'] and ref(path)==value,'Actual frozen source differs')
    preflight_ref=ref(OUTPUT/'CPU_METADATA_PREFLIGHT.json');preflight=bound(preflight_ref)
    controls=preflight['metadata_selfcheck'];require(preflight['schema']=='model_v3_fixed_h0_shadow_CPU_metadata_preflight_v3'
        and preflight['CPU_analysis_source_pins']==pins_ref
        and preflight['capture_producer_source_pins']==result['capture_producer_source_pins']
        and preflight['capture_producer_relabelled_as_v3'] is False
        and controls==dict(scope='SYNTHETIC_METADATA_PARSER_CONTROLS_ONLY',positive_controls=1,
            rejected_negative_controls=15,actual_job_claim=False), 'Actual metadata16 parser-control observation differs')
    require(preflight['actual_capture_accounting_validation']['original_row_count']==3
        and preflight['actual_capture_accounting_validation']['raw_stdout_filtered_or_rewritten'] is False,
        'Original capture accounting rows must be preserved')
    tiny=result['selfcheck'];require(tiny['dense_segment_oracle'] is True and tiny['row_R_four_way'] is True
        and 0<=tiny['closure']<=1e-10 and all(tiny['metadata'][key] is True for key in
            ('Git_NUL_empty_oracle','wrong_blob_rejected','nonallowlisted_projection_rejected')),'Actual tiny-head/metadata checks failed')
    parity=tiny['head_form_small_tensor_parity']
    require(len(parity)==4 and {(row['form'],row['pooling']) for row in parity}==
        {('H1','sum'),('H1','learned'),('H2','sum'),('H3','sum')}
        and all(math.isfinite(row['maxabs_FP32_vs_FP64']) and 0<=row['maxabs_FP32_vs_FP64']<=2e-6 for row in parity),
        'Original four tiny-head parity controls/threshold differ')
    cases=result['cases'];require(result['case_count']==len(cases)==48
        and [row['case_id'] for row in cases]==request['expected_case_ids'],'All original48 cases in exact order required')
    pairs={(field,transform) for field in ('p_extensive','p_dipole','p_dipole_magnitude')
        for transform in ('general_rotation','translation_only','other_rotation_and_translation')}
    stored32=[];stored64=[];recomputed64=[];gpu_closed=[];observations=0
    for case in cases:
        values=case['observations'];require(len(values)==9 and {(row['field'],row['transform']) for row in values}==pairs,
            'Every case must retain all3 fields x3 transforms')
        for row in values:
            require(row['not_FP32_acceptance'] is True,'Shadow result cannot assert physical FP32 acceptance')
            for name,target in (('CPU_FP32_closure',stored32),('FP64_closure',stored64)):
                value=row[name];require(type(value) in (int,float) and math.isfinite(value) and 0<=value<=1e-10,
                    'Saved closure exceeds unchanged fixed1e-10');target.append(value)
            terms={name:numbers(value) for name,value in row['signed_components'].items()}
            require(set(terms)=={'D','H','G','I','GPU_FP32_D','head_arithmetic_delta','CPU_FP32_D'}
                and len({len(value) for value in terms.values()})==1 and len(terms['D'])>0,'Exact saved signed-term shapes required')
            require(set(row['maxabs'])==set(terms) and all(row['maxabs'][name]==max(map(abs,value)) for name,value in terms.items()),
                'Saved maxabs summary differs from its saved terms')
            recomputed64.append(max(abs(d-h-g-i) for d,h,g,i in zip(terms['D'],terms['H'],terms['G'],terms['I'])))
            gpu_closed.append(max(abs(d-h-g-i-a) for d,h,g,i,a in zip(terms['GPU_FP32_D'],terms['H'],terms['G'],terms['I'],terms['head_arithmetic_delta'])))
            observations+=1
    require(result['field_transform_observations']==observations==432
        and max(recomputed64)<=1e-10 and max(gpu_closed)<=1e-10,'All432 saved component closures required')
    supervisor_ref=ref(O/'fixed_h0_shadow_cpu_v3_supervisor_4521503.json');supervisor=bound(supervisor_ref)
    require(supervisor['job_id']=='4521503' and supervisor['status']=='COMPLETED' and supervisor['exit_code']==0
        and supervisor['first_failure'] is None and supervisor['remaining']==[]
        and supervisor['gpu_initialization_permitted'] is False,'Actual CPU supervisor/process closure differs')
    private=supervisor['private_storage'];require(private['first_sampling_failure'] is None
        and private['last']['bytes']<=private['budget_bytes']==2<<30
        and supervisor['last_total_bytes']<2<<30,'Actual private/final-output budget failure')
    for path,sha in supervisor['sources_sha256'].items():require(ref(path)['sha256']==sha,'Actual supervisor source changed')
    receipt_ref=ref(O/'fixed_h0_shadow_CPU_v3_submission_v1.json');receipt=bound(receipt_ref)
    require(receipt['schema']=='model_v3_single_CPU_submission_v1' and receipt['job_id']=='4521503'
        and receipt['node']=='compute-0-13' and receipt['cpus']==16 and receipt['sbatch_returncode']==0
        and receipt['stdout'].split(';',1)[0].strip()=='4521503','Exact original CPU submission required')
    require(supervisor['command'][3]==str(SOURCE/'shadow_terminals_v1.py')
        and supervisor['command'][supervisor['command'].index('--source-pins-sha256')+1]==PIN,
        'Actual supervised CPU producer/source differs')
    argv=['sacct','-X','-n','-P','-j','4521503','--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
    start=time.time();process=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45,check=False)
    raw=dict(argv=argv,returncode=process.returncode,stdout=process.stdout,stderr=process.stderr,
        started_unix=start,completed_unix=time.time());raw_ref=write(args.accounting_output,raw)
    rows=[line.split('|') for line in process.stdout.splitlines() if line.strip()]
    require(process.returncode==0 and len(rows)==1 and rows[0][:4]==['4521503','zixiao','COMPLETED','0:0']
        and rows[0][5:] == ['16','compute-0-13'],'Fresh exact CPU parent C0/UID/allocation required')
    refs=dict(complete=complete_ref,result=complete['result'],CPU_source_pins=pins_ref,source_before=before_ref,source_after=after_ref,
        metadata_preflight=preflight_ref,supervisor=supervisor_ref,submission=receipt_ref,
        capture_complete=result['capture_complete'],capture_supervisor=result['capture_supervisor'],capture_accounting=result['capture_accounting'])
    for value in refs.values():require(ref(value['path'])==value,'Closed evidence drifted during review')
    for path,value in before.items():require(ref(path)==value,'Frozen source changed during review')
    closure=write(args.output,dict(schema='model_v3_Root_fixed_h0_shadow_CPU_actual_closure_v1',
        status='CPU_SHADOW_C0_METADATA_CLOSED_NOT_SCIENTIFIC_ADOPTION',authority='ROOT_ACTUAL_METADATA_REVIEW',
        actual_job_id='4521503',actual_accounting=raw_ref,closed_evidence=refs,
        full_source_entries=len(before),full_source_bytes=sum(value['bytes'] for value in before.values()),
        source_maps_before_after_equal=True,source_maps_match_complete_expected_inventory=True,all_actual_sources_rehashed_before_after=True,
        case_count=48,field_transform_observations=observations,metadata_parser_controls=controls,
        tiny_head_forms=len(parity),tiny_head_maxabs_FP32_vs_FP64=max(row['maxabs_FP32_vs_FP64'] for row in parity),
        tiny_four_way_closure=tiny['closure'],max_saved_CPU_FP32_closure=max(stored32),max_saved_FP64_closure=max(stored64),
        max_saved_terms_FP64_closure=max(recomputed64),max_saved_terms_GPU_four_way_closure=max(gpu_closed),
        closure_limit_unchanged=1e-10,original_FP32_threshold_changed=False,
        supervisor_remaining=supervisor['remaining'],private_storage_observation=private,
        private_cleanup_evidence='CPU supervisor first_failure=null includes storage.stop/final census; no separate deletion receipt asserted',
        CPU_adapter_version=3,capture_producer_relabelled=False,NPZ_model_or_SDK_payload_read=False,
        neural_forward_training_or_new_job_performed=False,scientific_adoption=False,FP32_equivariance_acceptance=False,
        not_a_replacement_for_sa4_attribution_report=True,closure_source=ref(__file__)))
    print(json.dumps(dict(status='ROOT_CPU_SHADOW_METADATA_CLOSED_NOT_SCIENTIFIC_ADOPTION',closure=closure,
        source_entries=len(before),cases=48,observations=432,max_saved_CPU_FP32_closure=max(stored32),
        max_saved_FP64_closure=max(stored64),max_saved_terms_GPU_four_way_closure=max(gpu_closed))))
    return 0


if __name__=='__main__':raise SystemExit(main())
