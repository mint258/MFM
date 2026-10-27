"""One Root metadata closure of the completed scientific failure4579; never models/NPZ."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

sys.dont_write_bytecode=True

B=Path('/share/home/zixiao/descriptor_analysis')
N=B/'runs/model_v3_20261026'
O=B/'runs/model_v3_20261025'
W=B/'MFM_model_v3_geometry_fp32_candidate_v1'
S=N/'geometry_fp32_e2e_v1_source'
JOB='4524579'
NODE='compute-0-21'
GPU='GPU-c35f2434-9137-9723-1af5-dc69b6295243'
LOCAL='03e26bea6a29ef96ba5611760763329207212741'
TREE='2d3b8f17e06d73bc2bc47745ccde982625646dd0'
PUBLIC='498ecbe7e88b1468067dde5692c10735fcadf2ea'
ROOT=O/('geometry_fp32_e2e_GPU_v1_'+JOB)
SUP=O/('geometry_fp32_e2e_GPU_v1_supervisor_'+JOB+'.json')
WORKER=O/('geometry_fp32_e2e_GPU_v1_launch_v1_worker_'+JOB+'.json')
ATTEMPT=O/'geometry_fp32_e2e_GPU_v1_submission_actual_v1.json'
FRAME=O/'geometry_fp32_e2e_GPU_v1_submission_actual_v1.admission.json'
LOG=O/('geometry_fp32_e2e_GPU_v1_launch_v1_'+JOB+'.log')
JOURNAL=SUP.with_suffix(SUP.suffix+'.jsonl')
STORAGE=SUP.with_suffix(SUP.suffix+'.storage.json')
FIELDS=('PD/p_extensive','PD/p_intensive','PD/d_intensive','PD/d_binary','PD/d_atom',
        'PD/p_pair','PD/p_gradient','PD/p_dipole','PD/p_dipole_magnitude',
        'S/noise','S/coordinate','S/element_logits','S/clean_bond_logits')
TRANSFORMS=('general_rotation','translation_only','other_rotation_and_translation')
WHOLE=2147483648
RSS=30064771072

def need(value,message):
    if not value:raise ValueError(message)

def reference(path,limit=2<<20):
    path=Path(path).absolute()
    need(path.suffix.lower() not in ('.npz','.pt','.pth','.wandb','.lmdb','.parquet','.pkl'),
         'No payload read/hash is permitted in this metadata closer')
    info=path.lstat()
    need(stat.S_ISREG(info.st_mode) and not path.is_symlink() and info.st_uid==1278
         and info.st_size<=limit,'Owned bounded ordinary source/metadata required: '+str(path))
    raw=path.read_bytes();after=path.stat()
    need((info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)==
         (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Metadata changed during reading')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def read(path,expected=None,limit=2<<20):
    actual=reference(path,limit)
    if expected is not None:need(actual==expected,'Actual metadata rawref differs: '+str(path))
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'Duplicate metadata key');result[key]=value
        return result
    value=json.loads(Path(path).read_bytes(),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON constant')))
    return value,actual

def bound(value,limit=2<<20):
    need(type(value) is dict and set(value)=={'path','bytes','sha256'},'Exact3-field rawref required')
    return read(value['path'],value,limit)[0]

def load_source(value,name):
    need(reference(value['path'],16<<20)==value,'Frozen metadata helper differs')
    spec=importlib.util.spec_from_file_location(name,value['path'])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def command(argv):
    result=subprocess.run(argv,capture_output=True,text=True,timeout=45)
    record=dict(argv=argv,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
    need(result.returncode==0 and result.stderr=='','Actual read-only command failed: '+repr(argv))
    return record

def finite(value):
    return type(value) in (int,float) and math.isfinite(value)

def same_parameters(current,old):
    need(current['all_named_parameter_sha256']==old['all_named_parameter_sha256']
         and current['parameters']==old['parameters'],'Original1492 complete seeded parameters differ')
    left,right=current['terminal_modules'],old['terminal_modules']
    need(set(left)==set(right),'Terminal module membership differs')
    for key in left:
        need(all(left[key][k]==right[key][k] for k in ('class','parameter_count','parameter_sha256')),
             'Original terminal parameter/class identity differs')
    # Squared norms are diagnostics, not cross-device/CPU-reduction identity.

def terminal_stat(value,case_dir,case_id):
    path=Path(value['path']).absolute()
    need(path.parent==case_dir and path.name==case_id+'__terminals.npz'
         and value['contains_native_data'] is False and value['contains_parameter_weights'] is False,
         'Exact model-owned terminal archive required')
    info=path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid==1278 and not path.is_symlink()
         and info.st_size==value['bytes']<=512*1024,'Terminal NPZ stat differs')
    arrays=value['arrays'];expected={role+'__'+name.replace('/','__')
        for role in ('original','transform0','transform1','transform2') for name in FIELDS}
    need(set(arrays)==expected and len(arrays)==52,'Exactly52 typed producer headers required')
    numeric=0
    for item in arrays.values():
        shape=item['shape']
        need(item['dtype']=='float32' and type(shape) is list and len(shape)==2
             and all(type(x) is int and x>0 for x in shape),'Actual nonempty FP32 header required')
        numeric+=4*shape[0]*shape[1]
    need(numeric==value['numeric_bytes']<=320*1024
         and re.fullmatch('[0-9a-f]{64}',value['sha256']),'Producer archive declaration differs')
    return dict(path=str(path),bytes=info.st_size,producer_sha256=value['sha256'],
        arrays=52,numeric_bytes=numeric,Root_check='stat and declared headers only; NPZ body not opened/rehashed/decoded',
        Root_reverified_NPZ_SHA=False)

def verify_case(row,index,old,request):
    path=Path(row['case_json']['path']).absolute()
    need(path.parent==ROOT/'cases'/('numeric_case_%02d'%index)
         and path.name==row['case_id']+'__numeric_case.json','Actual complete48 case path/order differs')
    value=bound(row['case_json']);m=value['measured'];c=value['construction']
    need(value['schema']=='model_v3_geometry_FP32_complete48_case_v1'
         and value['numeric_mode']==m['encoder_configuration']['head_config']['numeric_mode']=='compensated_fp32_v1'
         and value['attention_aggregation_mode']=='centered_fp32_v1'
         and value['attention_projection_mode']=='blocked_k64_compensated_fp32_v1'
         and value['all_FP32_residual_geometry_candidate'] is True
         and value['geometry_mode']==request['geometry_mode']=='residual_expansion_fp32_v1'
         and value['original_fixture_source_sha256']==request['original_fixed_fixture_source_sha256']
         and value['scientific_adoption'] is False and value['trained_or_selected_model'] is False,
         'Case used an undeclared method')
    need(m['schema']=='model_v3_composed_equivariance_v1_case'
         and m['case_id']==row['case_id']==c['case_id']
         and m['case']==old['case'] and m['fixture_native_atoms']==[3,9,32]
         and m['actual_native_data_reads']==0 and m['complete_terminal_count']==13,
         'Original case/fixture coverage differs')
    for key in ('fixture_geometry_sha256','original_physical_geometry_sha256','original_view_identity_sha256','registry_sha256'):
        need(m[key]==old[key],'Original1492 fixture/view/registry metadata differs')
    expected_config=deepcopy(old['encoder_configuration'])
    expected_config['backbone_config'].update(attention_aggregation_mode='centered_fp32_v1',
        attention_projection_mode='blocked_k64_compensated_fp32_v1',
        geometry_mode='residual_expansion_fp32_v1')
    need(m['encoder_configuration']==expected_config,'Configuration differs beyond the fixed declared numeric/aggregation/projection/geometry modes')
    same_parameters(m['weight_summary'],old['weight_summary'])
    need(c['original_parameter_sha256']==c['actual_parameter_sha256']==old['weight_summary']['all_named_parameter_sha256']
         and c['parameter_count']==m['weight_summary']['parameters']
         and c['all_six_aggregation_modes']==['centered_fp32_v1']*6
         and c['all_six_projection_modes']==['blocked_k64_compensated_fp32_v1']*6
         and c['FP64_core_or_encoder'] is False and c['new_parameters_or_initializer'] is False,
         'Actual all-layer/parameter construction differs')
    views=m['case']['views'];nodes=88 if views=='two' else 132;graphs=6 if views=='two' else 9
    need(m['encoder_forward_shapes']==[[nodes,512]]*4 and m['device']=='cuda:0',
         'Actual full packed6x512 forward shapes differ')
    geometry_ports=c['geometry_ports']
    dense=m['case']['distance_bias']=='C1-0'
    need(m['case']['distance_bias'] in ('C1-0','C1-a','C1-b'),'Original C1 case identity differs')
    expected_geometry=([('dense_layer',i,True) for _ in range(4) for i in range(6)]
        if dense else [('shared_pair_encoder',None,False)]*4)
    need(c['geometry_mode']==request['geometry_mode']=='residual_expansion_fp32_v1'
         and c['all_six_geometry_modes']==['residual_expansion_fp32_v1']*6
         and c['head_geometry_pooling_and_parameters_unchanged'] is True
         and c['NativeRuntimeDense_or_bf16_covered'] is False
         and c['geometry_spy_scope']=='One original raw-coordinate helper per call; no encoder replay or changed return'
         and c['geometry_backward_scope']=='Inline independent tiny controls only; full48 remains inference'
         and [(p['caller'],p['layer'],p['squared']) for p in geometry_ports]==expected_geometry
         and row['geometry_helper_calls']==len(geometry_ports)==(24 if dense else 4)
         and row['all_original_geometry_callers_four_frames_FP32'] is True,
         'Actual all-original geometry callers/modes/four-frame coverage differs')
    for port in geometry_ports:
        need(type(port['squared']) is bool and (port['layer'] is None or type(port['layer']) is int)
             and port['input_shape']==[graphs,32,3] and port['output_shape']==[graphs,32,32]
             and port['input_dtype']==port['output_dtype']=='torch.float32'
             and type(port['floating_operands_checked']) is int and port['floating_operands_checked']>0
             and type(port['floating_results_checked']) is int and port['floating_results_checked']>0
             and port['all_observed_geometry_floating_ports_CUDA_FP32'] is True
             and port['original_helper_called_once_and_original_result_returned'] is True
             and port['hardware_accumulator_proof'] is False,
             'Actual original geometry shape/FP32/transparent-call declaration differs')
    runtime=m['runtime']
    need(runtime['default_dtype']=='torch.float32' and runtime['float32_matmul_precision']=='highest'
         and runtime['TF32_matmul'] is False and runtime['TF32_cudnn'] is False
         and runtime['autocast_enabled'] is False and runtime['intraop_threads']==1
         and str(uuid.UUID(runtime['gpu_uuid'].removeprefix('GPU-')))==GPU[4:],
         'Original CUDA FP32 policy differs')
    ports=c['projection_ports'];expected_ports=[(i,k) for _ in range(4) for i in range(6) for k in ('qkv','out')]
    need([(p['layer'],p['projection']) for p in ports]==expected_ports
         and row['projection_helper_calls']==len(ports)==48 and row['all_twelve_sites_four_frames_FP32'] is True,
         'All12 projection sites in all4frames required')
    for p in ports:
        width=1536 if p['projection']=='qkv' else 512
        need(p['input_shape']==[graphs,32,512] and p['output_shape']==[graphs,32,width]
             and p['dense_rows']==graphs*32 and p['actual_K64_linear_calls']==8*((graphs*32+127)//128)
             and all(p[k]=='torch.float32' for k in ('input_dtype','weight_dtype','bias_dtype','output_dtype'))
             and p['floating_operands_checked']>0 and p['floating_results_checked']>0
             and p['all_observed_projection_floating_ports_CUDA_FP32'] is True
             and p['original_helper_called_once_and_original_result_returned'] is True,
             'Actual fixedK64/row128 FP32 helper trace differs')
    domain=m['domain']
    need(domain['domain_pass'] is True and domain['attention_scope']=='global/unbounded, no hard8 cutoff'
         and domain['default_cdist_MM_size_branch_exercised'] is True
         and domain['required_hard5_margin_A']==1e-4
         and domain['minimum_distance_to_hard5_boundary_A']>=1e-4,
         'Original physical test domain is not satisfied')
    need([x['transform']['name'] for x in m['measurements']]==list(TRANSFORMS),
         'All3 original transforms required')
    failures=0
    for move,old_move in zip(m['measurements'],old['measurements']):
        need(move['transform']==old_move['transform']
             and move['view_proof']['random_views_regenerated'] is False
             and move['view_proof']['discrete_view_identity_sha256']==m['original_view_identity_sha256']
             and move['vector_edges_unchanged'] is True
             and move['original_vector_edges']==move['transformed_vector_edges'],
             'Same original transform/noise/mask/edge identities required')
        fields=move['fields'];old_fields={f['field']:f for f in old_move['fields']}
        need([f['field'] for f in fields]==list(FIELDS),'All13 original typed fields required')
        passed=[]
        for f in fields:
            control=old_fields[f['field']]
            need(all(f[k]==control[k] for k in ('unit','law','count','components','nonzero_required','nonzero_norm_floor'))
                 and f['absolute_tolerance']==1e-5 and f['relative_tolerance']==0,
                 'Original unit/law/population/absolute criterion differs')
            if f['finite']:
                need(all(finite(f[k]) for k in ('maxabs','reference_max_row_norm','actual_max_row_norm'))
                     and f['maxabs']>=0,'Finite scalar measurement required')
                a=f['argmax'];need(type(a['row']) is int and 0<=a['row']<f['count']
                     and type(a['component']) is int and 0<=a['component']<f['components']
                     and finite(a['actual']) and finite(a['expected'])
                     and abs(a['actual']-a['expected'])==f['maxabs'],
                     'Same-component scalar max/argmax consistency differs')
                nonzero=f['reference_max_row_norm']>f['nonzero_norm_floor'] and f['actual_max_row_norm']>f['nonzero_norm_floor']
                verdict=f['maxabs']<=1e-5 and (nonzero or not f['nonzero_required'])
            else:
                need(f['maxabs'] is None and f['argmax'] is None,'Nonfinite measurements cannot fabricate extrema')
                verdict=False
            need(type(f['passed']) is bool and f['passed']==verdict,'Stored scalar absolute/nonzero verdict differs')
            passed.append(verdict);failures+=int(not verdict)
        need(move['passed']==all(passed),'Transform scalar verdict differs')
    verdict=all(x['passed'] for x in m['measurements'])
    need(m['passed']==row['passed']==verdict and type(verdict) is bool,'Case failure criterion differs')
    need(m['actual_terminal_output_artifact']==row['actual_terminal_output_artifact'],'Producer NPZ declaration differs')
    artifact=terminal_stat(m['actual_terminal_output_artifact'],path.parent,row['case_id'])
    return dict(case_id=row['case_id'],passed=verdict,case_json=row['case_json'],failed_field_observations=failures,
        geometry_helper_calls=len(geometry_ports),projection_helper_calls=len(ports)),artifact

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();started=time.time()
    own=reference(__file__)
    need(own['sha256']==args.source_sha256 and os.getuid()==1278
         and socket.gethostname()=='sonmi' and not os.environ.get('SLURM_JOB_ID'),
         'Exact source/Root login metadata coordinator required')
    need(not args.output.exists() and args.output.absolute().parent==N,'Fresh direct Root metadata output required')
    attempt,attempt_ref=read(ATTEMPT);frame,frame_ref=read(FRAME);worker,worker_ref=read(WORKER)
    need(attempt['status']=='SUBMITTED' and attempt['job_id']==worker['job_id']==JOB
         and worker['status']=='CHILD_RETURNED' and worker['child_exit_code']==1
         and attempt['inputs']==worker['inputs']==frame['inputs']
         and attempt['admission_frame']==frame_ref==worker['immutable_admission_frame']
         and worker['submission_receipt']==attempt_ref,'Actual attempt/frame/worker source chain differs')
    inputs=attempt['inputs'];pins=bound(inputs['launch_source_pins']);request=bound(inputs['diagnostic_source_pins'])
    need(inputs['node']==NODE and inputs['gpu_uuid']==GPU and request['node']==NODE and request['gpu_uuid']==GPU
         and pins['execution_request']==inputs['diagnostic_source_pins']
         and len(pins['files'])==9 and len(request['source_refs'])==1197,
         'Final source-bound request/pins scope differs')
    expected={x['path']:x for x in request['source_refs']+pins['files']+pins['protected_dependencies']}
    expected[str(S/'source_pins_v1.json')]=inputs['launch_source_pins']
    before,before_ref=read(ROOT/'sources_before.json');after,after_ref=read(ROOT/'sources_after.json')
    need(before==after==expected and len(expected)==1198,'Actual complete1198 before/after source scope differs')
    for path,value in expected.items():need(reference(path,16<<20)==value,'Current source drift')
    pub_ref=next(x for x in pins['files'] if x['path']==str(S/'geometry_publication.py'))
    pub=load_source(pub_ref,'Root_geometry4579_frozen_publication')
    public_rows=pub.verify_publication(request)
    # Frozen verifier checks actual same-code4576 fourXML/full116 and all7
    # candidate+9method+2metadata published byte/blob rows, without a model import.
    need(len(public_rows)==18 and inputs['public_blob_preflight']==public_rows,
         'Actual source-bound prelaunch candidate/full/method metadata rows differ')
    full_cpu=bound(request['full_cpu_root_closure'])
    need(len(full_cpu['XML'])==4,'Actual full CPU fourXML refs must remain explicit')
    need(request['schema']=='model_v3_geometry_FP32_complete48_GPU_request_v1'
         and request['status']=='FINAL_BOUND_PUBLIC_GEOMETRY_FP32_REQUEST'
         and request['executable'] is True and request['expected_case_count']==48
         and request['expected_original_encoder_forwards']==192
         and request['expected_geometry_helper_calls']==512 and request['expected_projection_helper_calls']==2304
         and request['absolute_tolerance']==1e-5 and request['relative_tolerance']==0
         and request['new_terminals_expected_bitwise_equal_to_4550'] is False
         and pins['case_count']==48 and pins['scientific_encoder_forwards']==192
         and pins['full_FP64_encoder_forwards']==0 and pins['expected_geometry_helper_calls']==512
         and pins['geometry_mode']=='residual_expansion_fp32_v1'
         and pins['wall_seconds']==1100 and pins['RSS_bytes']==RSS
         and pins['whole_output_bytes']==pins['private_bytes']==WHOLE,
         'Final exact geometry scope/unchanged policy and limits differ')
    guard=load_source(inputs['resource_guard'],'Root_geometry4579_frozen_d3_resource_metadata')
    need(guard.NODE==NODE and guard.MEMORY_MIB==32768 and guard.RSS_BYTES==RSS
         and guard.OUTPUT_BYTES==WHOLE and guard.WALL_SECONDS==1100,'Original resource guard limits differ')
    rebuilt=guard.root_resource_evidence(list(frame['Root_resources']['observations'].values()),inputs,
        frame['Root_resources']['resources'],frame['Root_resources']['quota'])
    need(rebuilt==frame['Root_resources'],'Original raw Root resource/quota binding differs')
    guard.verify_root_resources(frame['Root_resources'],inputs,now=datetime.fromisoformat(worker['started_utc']))
    need(worker['resources']['Root_frame_body_sha256']==frame['Root_resources']['body_sha256']
         and worker['resources']['worker_claims_Root_capture_is_live'] is False
         and all(0<=v<=120 for v in worker['resources']['Root_capture_ages_seconds'].values())
         and Decimal(worker['resources']['bound_commitment_MiB'])<Decimal('.85')*Decimal(worker['resources']['effective_RealMemory_MiB'])
         and Decimal(worker['resources']['actual_local_MemAvailable_MiB'])-32768>=Decimal('.15')*Decimal(worker['resources']['effective_RealMemory_MiB'])
         and worker['resources']['current_GPU']['gpu_uuid']==GPU
         and worker['resources']['current_GPU']['foreign_applications']==[],
         'Recorded actual on-node resource admission differs')
    allocation=worker['actual_allocation_identity']
    need(allocation['uid']==1278 and allocation['job_id']==JOB and allocation['node']==NODE
         and allocation['cpus_per_task']==16 and allocation['memory_per_node_MiB']==32768
         and '/job_'+JOB+'/' in allocation['cgroup']
         and worker['public_GPU_lock']['uid']==1278 and worker['public_GPU_lock']['fd']==9
         and worker['public_GPU_lock']['kernel_exclusive_lock_acquired_or_revalidated'] is True,
         'Actual allocation/public lock proof differs')
    sb=[x for x in attempt['observations'] if x['argv']==['sbatch','--parsable','--export=ALL','--nodelist='+NODE,str(S/'run_geometry_matrix_GPU_v1.sbatch')]]
    need(len(sb)==1,'One actual sbatch raw observation required')
    submitted_job=re.fullmatch(r'(\d+)(?:;[A-Za-z0-9_.-]+)?',guard.checked_observation(sb[0],sb[0]['argv']).strip())
    need(submitted_job is not None and submitted_job[1]==JOB,'Exact actual sbatch job binding differs')
    submitted=datetime.fromisoformat(attempt['sbatch_completed_utc'])
    publication_chronology={}
    for key in ('method_publication','metadata_publication'):
        proof=bound(request[key])
        need(datetime.fromisoformat(proof['actual_utc'].replace('Z','+00:00'))<=submitted,
             'Actual method/metadata publication timestamp must precede submission')
        publication_chronology[key]=dict(reference=request[key],actual_utc=proof['actual_utc'],
            checked_before_sbatch_completed_utc=attempt['sbatch_completed_utc'])
    # The immutable candidate receipt has no timestamp field. Do not invent one
    # or treat current mtime as a past API time: bind the exact candidate/full
    # verifier rows already persisted in Root submission/frame/worker inputs.
    candidate_publication=bound(request['publication_receipt'])
    need('actual_utc' not in candidate_publication and candidate_publication['public_code_sha']==PUBLIC
         and candidate_publication['full_CPU_closure']==request['full_cpu_root_closure']
         and datetime.fromisoformat(attempt['started_utc'])<=submitted
         and datetime.fromisoformat(worker['started_utc'])>=submitted,
         'Candidate prelaunch evidence/recorded chronology differs')
    publication_chronology['candidate']=dict(reference=request['publication_receipt'],actual_API_timestamp=None,
        chronology_scope='Exact source/public/full verification rows persisted in immutable prelaunch Root inputs; no independent candidate API timestamp reconstructed',
        prelaunch_inputs_match_reverified_rows=True)
    sacct=command(['sacct','-X','-n','-P','-j',JOB,'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'])
    need(sacct['stdout'].strip().split('|')==[JOB,'zixiao','FAILED','1:0','64','16',NODE],
         'Actual failed scientific Slurm parent differs; never pretend C0')
    git={}
    for name,argv,want in (
        ('head',['git','-C',str(W),'rev-parse','HEAD'],LOCAL),
        ('tree',['git','-C',str(W),'rev-parse','HEAD^{tree}'],TREE),
        ('branch',['git','-C',str(W),'branch','--show-current'],'model-v3-geometry-fp32-candidate-20261028-v1'),
        ('clean',['git','-C',str(W),'status','--porcelain=v1','--untracked-files=all'],'')):
        git[name]=command(argv);need(git[name]['stdout'].strip()==want,'Current candidate Git identity/clean state differs')
    result,result_ref=read(ROOT/'RESULT.json')
    counts=dict(tests=48,failures=33,errors=0,skipped=0)
    need(result['schema']=='model_v3_geometry_FP32_complete48_GPU_result_v1'
         and result['status']=='PHYSICAL_CRITERION_FAIL' and result['failure'] is None
         and result['counts']==counts and result['pytest_exit_code']==1
         and result['ordinary_all_arithmetic_FP32_encoder_forwards']==result['actual_complete_geometry_candidate_encoder_forwards']==192
         and result['full_FP64_encoder_forwards']==0 and result['actual_projection_helper_calls']==2304
         and result['geometry_mode']=='residual_expansion_fp32_v1'
         and result['actual_geometry_helper_calls']==512 and result['all_original_geometry_callers_observed'] is True
         and result['new_terminals_expected_bitwise_equal_to_4550'] is False
         and result['actual_native_data_reads']==0
         and result['all_twelve_sites_four_frames_observed'] is True and result['source_before_after_equal'] is True
         and result['formal_FP32_composed_test_pass'] is False and result['scientific_adoption'] is False
         and result['local_commit']==LOCAL and result['public_commit']==PUBLIC and result['exact_shared_tree']==TREE,
         'Actual complete failed physical matrix metadata differs')
    tree=ET.parse(ROOT/'matrix.xml');xml_counts={k:sum(int(x.get(k,'0')) for x in tree.iter('testsuite')) for k in counts}
    need(xml_counts==counts,'Actual complete48 JUnit differs')
    ids=request['expected_case_ids']
    need([x['case_id'] for x in result['cases']]==ids and len(ids)==len(set(ids))==48,
         'Exact ordered complete48 required')
    need({x.get('name').split('[')[-1].removesuffix(']') for x in tree.iter('testcase')}==set(ids),
         'JUnit membership differs')
    capture=bound(request['original_capture_manifest'])
    need(capture['job_id']=='4521492' and capture['status']=='CAPTURE_COMPLETE','Original parameter authority differs')
    old_refs={x['case_id']:x['capture_case'] for x in capture['cases']}
    case_rows=[];artifacts=[]
    for index,row in enumerate(result['cases']):
        old=bound(old_refs[row['case_id']])['original_measurement']
        value,artifact=verify_case(row,index,old,request);case_rows.append(value);artifacts.append(artifact)
    need(sum(x['passed'] for x in case_rows)==15 and sum(not x['passed'] for x in case_rows)==33,
         'Stored scalar case outcome differs')
    need(sum(x['geometry_helper_calls'] for x in case_rows)==512
         and sum(x['projection_helper_calls'] for x in case_rows)==2304,
         'Actual full48 geometry/projection counts differ')
    geometry_tiny,tiny_ref=read(ROOT/'INLINE_TINY_CANDIDATE_CONTROLS.json')
    need(geometry_tiny['scope']=='INLINE_ACTUAL_GEOMETRY_AND_ORIGINAL_PROJECTION_HELPERS_NOT_FULL48'
         and geometry_tiny['geometry_mode']=='residual_expansion_fp32_v1'
         and geometry_tiny['geometry_tile_rows']==65536 and geometry_tiny['splitter']==4097.
         and geometry_tiny['independent_second_direction']==26.
         and geometry_tiny['norm_gradient_oracle_absolute_tolerance']==2e-7
         and geometry_tiny['encoder_forwards']==geometry_tiny['scientific_cases_added']==0
         and geometry_tiny['FP64_arithmetic'] is False and geometry_tiny['scientific_adoption'] is False
         and all(geometry_tiny[k] is True for k in ('CPU_and_CUDA_RNG_unchanged',
             'raw_difference_tail_exact_squared_oracle','analytic_first_derivatives','all_three_second_cross_blocks',
             'norm_3_4_5_and_transverse_Hessian','zero_norm_and_zero_derivative_convention',
             'nonFP32_guard_inputs_not_arithmetic'))
         and geometry_tiny['guard_rejections']==['torch.float64','torch.bfloat16','torch.float16','active_cuda_autocast'],
         'Actual geometry independent26/first/second/zero/norm/guard controls differ')
    tiny=geometry_tiny['original_projection_controls']
    need(tiny['scope']=='INLINE_TINY_ACTUAL_K64_FP32_HELPER_NOT_FULL48' and tiny['K_block']==64
         and tiny['dense_row_tile']==128 and tiny['encoder_forwards']==tiny['scientific_cases_added']==0
         and tiny['FP64_arithmetic'] is False and tiny['independent_second_direction']==56.3125
         and all(tiny[k] is True for k in ('cancellation_bias_once','independent_all_first_derivatives',
             'independent_all_Hessian_vector_blocks','CPU_and_CUDA_RNG_unchanged'))
         and tiny['guard_rejections']==['torch.float64','torch.bfloat16','torch.float16','active_cuda_autocast'],
         'Actual inline helper/gradient/guard/RNG controls differ')
    admission,admission_ref=read(ROOT/'CUDA_UUID_ADMISSION.json')
    need(admission['job_id']==JOB and admission['node']==NODE and admission['gpu_uuid']==GPU
         and admission['gpu_uuid_observation']['canonical']==GPU
         and admission['gpu_uuid_observation']['raw_type']=='torch._C._CUuuid'
         and str(uuid.UUID(bytes=bytes(admission['gpu_uuid_observation']['raw_CUuuid_bytes'])))==GPU[4:],
         'Actual strict full GPU UUID/CUuuid admission differs')
    sup,sup_ref=read(SUP)
    need(sup['status']=='FAILED' and sup['exit_code']==1 and sup['job_id']==JOB
         and sup['first_failure']==dict(phase='child_exit',exit_code=1)
         and sup['remaining_recorded_processes_before_retirement']==[]
         and sup['private_storage_cleanup_errors']==[] and sup['foreign_gpu_processes_signalled'] is False
         and sup['private_storage_final']['first_sampling_failure'] is None
         and sup['private_storage_final']['budget_bytes']==sup['output_budget_bytes']==WHOLE
         and sup['supervisor_source_sha256']==request['supervisor_source']['sha256'],
         'Original on-node scientific exit/resource/private cleanup proof differs')
    expected_child=[request['GPU_python'],'-u','-B',str(S/'run_geometry_matrix.py'),'--request',
        str(S/'execution_request_v1.json'),'--request-sha256',inputs['diagnostic_source_pins']['sha256'],'--output-root',str(ROOT)]
    need(sup['command']==sup['launch_identity']['argv']==expected_child and sup['launch_identity']['uid']==1278
         and sup['launch_identity']['slurm_job_id']==JOB and sup['gpu_uuid']==GPU,
         'Actual supervised child identity differs')
    monitor_ref=expected[str(B/'MFM_model_v3/tools/model_v3/runtime_monitor.py')]
    monitor=load_source(monitor_ref,'Root_geometry4579_frozen_output_census')
    samples=[];identities={}
    with JOURNAL.open() as stream:
        for line in stream:
            need(len(line)<=1<<20 and len(samples)<10000,'Bounded resource metadata journal required')
            value=json.loads(line);samples.append(value)
            need(value['processes']['rss_sum_bytes']<=RSS
                 and value['output_bytes']<=WHOLE
                 and value['gpu']['uuid']==GPU and value['gpu']['foreign_processes']==[]
                 and value['gpu']['used_bytes']<=.85*value['gpu']['total_bytes']
                 and value['private_storage']['first_sampling_failure'] is None,
                 'Original sampled resource guard data differs')
            for row in value['processes']['processes']:
                if 'identity' in row:identities[(row['identity']['pid'],row['identity']['start_ticks'])]=row['identity']
    need(samples,'Actual resource samples required')
    external=[ATTEMPT,FRAME,SUP,JOURNAL,STORAGE,LOG,WORKER]
    seen=set();external_rows=[];total=monitor.owned_output_bytes(ROOT)
    root_bytes=total
    for path in external:
        st=path.lstat();need(stat.S_ISREG(st.st_mode) and st.st_uid==1278 and not path.is_symlink(),'Ordinary disjoint external control required')
        need(not path.is_relative_to(ROOT),'External path overlaps child root')
        if (st.st_dev,st.st_ino) not in seen:
            seen.add((st.st_dev,st.st_ino));total+=st.st_size;external_rows.append(dict(path=str(path),bytes=st.st_size))
    total+=sup['private_storage_final']['last']['bytes']+(2<<20)
    need(total<=WHOLE and worker['closed_control_output_census']['cap_bytes']==WHOLE
         and worker['closed_control_output_census']['conservative_total_bytes']<=WHOLE,
         'Current complete family plus conservative closure allowance exceeds2GiB')
    need(not any(x.split('.')[0] in {'torch','numpy','wandb','rdkit','phychem_mfm'} for x in sys.modules),
         'This Root closer must never import model/SDK/array/native packages')
    closure=dict(schema='model_v3_Root_complete48_geometry_FP32_scientific_failure_closure_v1',
        status='ACTUAL_COMPLETE48_GEOMETRY_FP32_SCIENTIFIC_CRITERION_FAIL_15_PASS_33_FAIL_SOURCE_RESOURCE_CLOSED',
        job_id=JOB,actual_unix=time.time(),closure_source=own,actual_sacct=sacct,current_candidate_Git=git,
        submission=attempt_ref,admission_frame=frame_ref,worker=worker_ref,supervisor=sup_ref,
        request=inputs['diagnostic_source_pins'],source_pins=inputs['launch_source_pins'],
        result=result_ref,matrix_xml=reference(ROOT/'matrix.xml',16<<20),
        source_before=before_ref,source_after=after_ref,all_sources_before_after_current_equal=True,
        current_source_count=len(expected),request_source_count=len(request['source_refs']),
        metadata_publication_rows_verified=len(public_rows),publication_chronology=publication_chronology,
        candidate_full_CPU_root=request['full_cpu_root_closure'],candidate_full_CPU_four_XML=full_cpu['XML'],
        case_count=48,counts=counts,
        encoder_forwards=192,actual_FP32_forwards=192,actual_FP64_encoder_forwards=0,
        projection_helper_calls=2304,all12sites4frames_observed=True,
        geometry_helper_calls=512,all_original_geometry_callers4frames_observed=True,
        geometry_mode='residual_expansion_fp32_v1',
        new_terminals_expected_bitwise_equal_to_4550=False,
        terminal_array_count=48*52,all_case_JSON_current_rawrefs_verified=True,
        case_scalar_rows=case_rows,terminal_artifacts=artifacts,
        terminal_payload_decoded_or_rehashed_on_login=False,NPZ_SHA_attribution='Original producer only; Root checked stat/header declarations',
        tiny_controls=tiny_ref,UUID_admission=admission_ref,
        no_infrastructure_failure_seen=True,Slurm_parent_is_NOT_C0=True,
        private_cleanup_and_recorded_processes_closed=True,foreign_processes_signalled=False,
        process_scope='Original source-bound on-node cleanup proof and terminal Slurm only; no new remote process scan or signal',
        resource_samples=dict(count=len(samples),recorded_bound_process_identities=len(identities),sampled_max_RSS_bytes=max(x['processes']['rss_sum_bytes'] for x in samples),
            sampled_max_GPU_used_bytes=max(x['gpu']['used_bytes'] for x in samples),
            sampled_max_output_bytes=max(x['output_bytes'] for x in samples),
            peak_semantics='Sampled maxima are lower bounds, not exact lifetime peaks'),
        current_whole_census=dict(child_root_bytes=root_bytes,external_files=external_rows,
            conservative_private_final_snapshot_bytes=sup['private_storage_final']['last']['bytes'],
            Root_closure_maximum_allowance_bytes=2<<20,conservative_total_bytes=total,cap_bytes=WHOLE,
            original_owned_output_bytes_used=True,NPZ_access='stat-only by census'),
        old_formal_FP32_result_unchanged=dict(passed=21,failed=27,no_old_artifact_written=True),
        old_projection4550_result_unchanged=dict(passed=12,failed=36,no_old_artifact_written=True),
        formal_FP32_gate_satisfied=False,model_freeze_candidate=False,scientific_adoption=False,
        closure_success_is_not_experiment_success=True,elapsed_metadata_seconds=time.time()-started)
    raw=(json.dumps(closure,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(raw)<=2<<20,'Root metadata closure exceeds declared allowance')
    with args.output.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    print(json.dumps(dict(status=closure['status'],closure=reference(args.output),experiment_parent='FAILED1:0',
                         counts=counts,science_accepted=False)))
    return 0

if __name__=='__main__':raise SystemExit(main())
