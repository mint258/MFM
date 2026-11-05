"""Manual R2 A-v2 source/publication guard only; no model, numeric audit or payload imports."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, math, os, re, stat, subprocess
from pathlib import Path

B=Path('/share/home/zixiao/descriptor_analysis'); N=B/'runs/model_v3_20261026'; O=B/'runs/model_v3_20261025'
W=B/'MFM_model_v3_A_acceptance_v2_candidate_v1'; HERE=Path(__file__).absolute().parent
FAMILY=N/'performance_manual_R2_Av2_v1'; OUT=FAMILY/'child'; CONTROL=FAMILY/'control'
CODE='7ffe8a5557590b1481f4ca74073007f070dc6a50'; PUBLIC='2b4a4df8636e5d65915d535472ba01084ea72dab'
TREE='8f9530415034bdb885c1c765aee434797c70e7c7'
GPU='GPU-c35f2434-9137-9723-1af5-dc69b6295243'; NODE='compute-0-21'
RULE_PUBLIC='4f6ba16973ea4a30472c7fb33d3aadec974a4462'
EXEC_SHA='7cabbd4a0300d551154ffb9bcbed5466fc9886d0eb886a1ae37ee3e7f70db46e'
ZERO={f'backbone.layers.{i}.attn.dist_mlp.2.bias' for i in range(6)}
LIMIT=2<<30; RSS=56<<30; META=2<<20
FILES=('run_manual_R2_Av2.sbatch','Root_submit_v1.py','source_guard.py','dependencies.json','METHODS_README.md','source_pins.json')
PREFIX='docs/model_v3/pre_registered_methods/performance_manual_R2_Av2_v1/'

def need(ok,message):
    if not ok:raise ValueError(message)

def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def reference(path,maximum=META):
    path=Path(path).absolute();before=path.lstat()
    need(path.resolve()==path and stat.S_ISREG(before.st_mode) and before.st_uid==1278
         and before.st_nlink==1 and before.st_size<=maximum,'Owned canonical bounded metadata/source required: '+str(path))
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    after=path.lstat()
    need(tuple(getattr(before,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns'))==
         tuple(getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns')),'Source/metadata changed while read')
    return dict(path=str(path),bytes=before.st_size,sha256=h.hexdigest())

def read(path,maximum=META):
    ref=reference(path,maximum);value=json.loads(Path(path).read_bytes(),
        parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    need(reference(path,maximum)==ref,'Metadata changed during parse')
    return value,ref

def bound(ref):
    value,current=read(ref['path']);need(current==ref,'Actual metadata rawref differs');return value

def number(value):
    need(type(value) in (int,float) and math.isfinite(value) and value>=0,'Finite nonnegative actual observation required')
    return value

def parent(raw,job,*,node,positive=True):
    need(raw['argv']==['sacct','-X','-n','-P','-j',job,
         '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
         and type(raw['returncode']) is int and raw['returncode']==0 and raw['stderr']=='','Actual exact parent accounting required')
    rows=[r.split('|') for r in raw['stdout'].splitlines() if r.strip()]
    need(len(rows)==1 and len(rows[0])==7 and rows[0][0:2]==[job,'zixiao']
         and rows[0][4].isdigit() and rows[0][5:]==['16',node],'Owned exact16CPU parent identity differs')
    if positive:need(rows[0][2:4]==['COMPLETED','0:0'],'Actual parent C0 required')
    return rows[0]

def verify_method(ref):
    receipt=bound(ref)
    need(receipt['schema']=='model_v3_exact_tree_publication_actual_v1'
         and receipt['repository_full_name']=='mint258/MFM' and receipt['branch']=='model-v3'
         and receipt['public_branch_readback_verified'] is True
         and receipt['public_Git_API_tree_readback_verified'] is True,'Actual method publication/readbacks required')
    table={r['path']:r for r in receipt['files']}
    need(len(table)==len(receipt['files']),'Duplicate published method paths')
    for name in FILES:
        raw=(HERE/name).read_bytes();item=table[PREFIX+name]
        need(item['type']=='blob' and item['sha']==hashlib.sha1(
            b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),'Method blob differs: '+name)
    return receipt

def verify_package(pin_sha):
    pins,ref=read(HERE/'source_pins.json');need(ref['sha256']==pin_sha,'Root-bound package SHA required')
    need(pins['schema']=='model_v3_manual_R2_Av2_GPU_source_pins_v1'
         and {Path(r['path']).name for r in pins['files']}==set(FILES)-{'source_pins.json'}
         and len(pins['files'])==5,'Exact five source leaves and separate pins required')
    for row in pins['files']:
        need(Path(row['path']).parent==HERE and reference(row['path'])==row,'Frozen source bytes differ')
    return ref

def validate_sources():
    """Current tested/published source qualification; runs only when explicitly called."""
    d,_=read(HERE/'dependencies.json');refs=d['raw_refs']
    for ref in refs.values():need(reference(ref['path'])==ref,'Dependency rawref differs')
    pub=bound(refs['publication']);full=bound(refs['full_CPU_Root_closure'])
    need(pub['schema']=='model_v3_exact_tree_publication_actual_v1'
         and pub['branch']=='model-v3-a-acceptance-v2-20261028-v1'
         and pub['repository_full_name']=='mint258/MFM'
         and (pub['local_code_sha'],pub['public_code_sha'],pub['tree_sha'])==(CODE,PUBLIC,TREE)
         and pub['public_branch_readback_verified'] is True and pub['public_Git_API_tree_readback_verified'] is True
         and pub['full_cpu_root_closure']==refs['full_CPU_Root_closure'],'Exact new source publication differs')
    need(full['schema']=='model_v3_candidate_single_parent_full_Root_closure_auto_memory_v1'
         and full['status']=='ACTUAL_C0_FULL_CORE_SUITE_SOURCE_AND_AUTOMATIC_MEMORY_OPERATIONAL_CLOSED'
         and (full['job_id'],full['code_commit'],full['tree'])==('4524695',CODE,str(W))
         and full['counts']==dict(tests=2676,failures=0,errors=0,skipped=3)
         and full['passed']==2673 and full['test_file_count']==115 and full['pytest_children']==4
         and full['all_runtime_before_after_and_current_verified'] is True
         and full['closure_source_pins']==refs['full_CPU_closer_source_pins'],'Actual complete115 same-source CPU closure required')
    parent(full['actual_sacct'],'4524695',node='compute-0-18')
    producer=bound(refs['full_CPU_closer_source_pins'])
    need(producer['schema']=='model_v3_candidate_full_auto_memory_Root_closer_sources_v1'
         and refs['full_CPU_closer_source_pins']['sha256']=='7be257ef58825543c1a2b870096f1e1035e218e48393ee2a5f8d0c79bfee5cb5'
         and len(producer['files'])==3,'Exact audited auto-memory CPU producer required')
    producer_root=Path(refs['full_CPU_closer_source_pins']['path']).parent
    for row in producer['files']:
        need(reference(producer_root/row['file'])==dict(path=str(producer_root/row['file']),
             bytes=row['bytes'],sha256=row['sha256']),'Actual Root closer source changed')
    need(full['selected_input_rawrefs_before']==full['selected_input_rawrefs_after']
         and full['Slurm_memory_mode']=='automatic_default' and full['requested_memory_MiB'] is None
         and full['software_working_memory_budget_bytes']==32<<30
         and full['automatic_memory_observation']['Slurm_memory_allocation_guarantee_claimed'] is False,
         'Actual CPU automatic-memory provenance differs; it does not modify this GPU64G policy')
    before=bound(full['source_before']);after=bound(full['source_after']);summary=bound(full['summary'])
    need(before==after==summary['sources_before']==summary['sources_after']
         and before['runtime_sha256']==full['current_runtime_sha256']
         and summary['status']=='PASS' and summary['failure'] is None
         and summary['job_id']=='4524695' and summary['code_commit']==CODE
         and summary['test_file_count']==115 and summary['counts']==full['counts']
         and summary['workers']==4 and len(summary['shards'])==4,'Actual CPU summary/source scope differs')
    union=[name for row in summary['shards'] for name in row['files']]
    need(len(union)==len(set(union))==115 and set(union)==set(summary['all_test_file_sha256'])
         and all(row['returncode']==0 for row in summary['shards']),'Actual full115 module union differs')
    for name,digest in before['runtime']['project_source_sha256'].items():
        relative=Path(name);need(not relative.is_absolute() and '..' not in relative.parts,'Relative complete source name required')
        need(reference(W/relative)['sha256']==digest,'Current source differs from actual full CPU')
    for row in before['runtime']['external_source_refs'].values():
        need(reference(row['path'])['sha256']==row['sha256'],'Current external interpretation source differs')
    for row in pub['files']:
        raw=(W/row['path']).read_bytes()
        need(row['type']=='blob' and hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==row['sha'],
             'Current candidate authored source differs from public blob')
    rule=bound(refs['rule_publication'])
    need(rule['schema']=='model_v3_exact_tree_publication_actual_v1' and rule['public_code_sha']==RULE_PUBLIC
         and rule['public_branch_readback_verified'] is True and rule['public_Git_API_tree_readback_verified'] is True
         and rule['source_document']==refs['rule_document'],'Exact published new gradient rule document required')
    options=bound(refs['candidate_options']);execution=bound(refs['manual_execution']);anchor=bound(refs['all_on_R2_configuration'])
    need(options==anchor['candidate'] and all(options[k] is True and type(options[k]) is bool
         for k in ('backbone_checkpointing','distance_checkpointing','head_checkpointing'))
         and options['precision']=='fp32' and options['fused_adamw'] is False
         and options['tf32'] is False and options['compile_backbone'] is False,'Exact original a00 model/options required')
    need(execution==dict(schema='model_v3_performance_execution_v1',checkpoint_policy='manual')
         and refs['manual_execution']['bytes']==85 and refs['manual_execution']['sha256']==EXEC_SHA,
         'Original85-byte manual observation required; no packing or auto/profile relabel')
    need(anchor['seed']==0 and anchor['input']=='native_s' and anchor['smoke'] is False
         and anchor['data_version']['sampler']['max_padded_cost']==8000000
         and anchor['data_version']['sampler']['padded_cost_multiplier']==3
         and anchor['data_version']['loader']['num_workers']==8
         and anchor['original_shard_snapshot_prejob_sha256']==refs['S_original_snapshot']['sha256'],
         'Historical data/options anchor differs; its old code is not new qualification')
    return dict(refs=refs,anchor=anchor,CPU=refs['full_CPU_Root_closure'],
                source_count=len(before['runtime']['project_source_sha256']),
                external_source_count=len(before['runtime']['external_source_refs']))

