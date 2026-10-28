"""Posthoc4704 metadata reader: zero-based fixed20 indices only; no model or payload imports."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, math, os, re, stat, subprocess
from pathlib import Path

B=Path('/share/home/zixiao/descriptor_analysis'); N=B/'runs/model_v3_20261026'; O=B/'runs/model_v3_20261025'
W=B/'MFM_model_v3_A_acceptance_v2_candidate_v1'; HERE=N/'performance_A5_R2_GPU_v2_source'
FAMILY=N/'performance_A5_R2_v2'; OUT=FAMILY/'child'; CONTROL=FAMILY/'control'
CODE='7ffe8a5557590b1481f4ca74073007f070dc6a50'; PUBLIC='2b4a4df8636e5d65915d535472ba01084ea72dab'
TREE='8f9530415034bdb885c1c765aee434797c70e7c7'
GPU='GPU-c35f2434-9137-9723-1af5-dc69b6295243'; NODE='compute-0-21'
RULE_PUBLIC='4f6ba16973ea4a30472c7fb33d3aadec974a4462'
EXEC_SHA='30467f4ce4bfaf6b752fe697ff35614527575d3af799aa07f8b8673605d3ccbb'
ZERO={f'backbone.layers.{i}.attn.dist_mlp.2.bias' for i in range(6)}
LIMIT=2<<30; RSS=56<<30; META=2<<20
FILES=('run_A5_R2.sbatch','Root_submit_v2.py','close_A5_R2_v2.py','dependencies.json','METHODS_README.md','source_pins.json')
PREFIX='docs/model_v3/pre_registered_methods/performance_A5_R2_v2/'

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
    need(pins['schema']=='model_v3_A5_R2_GPU_v2_source_pins_v1'
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
    options=bound(refs['candidate_options']);execution=bound(refs['A5_execution']);anchor=bound(refs['all_on_R2_configuration'])
    need(options==anchor['candidate'] and all(options[k] is True and type(options[k]) is bool
         for k in ('backbone_checkpointing','distance_checkpointing','head_checkpointing'))
         and options['precision']=='fp32' and options['fused_adamw'] is False
         and options['tf32'] is False and options['compile_backbone'] is False,'Exact original a00 model/options required')
    need(execution==dict(schema='model_v3_performance_execution_v1',checkpoint_policy='manual',
         padding=dict(mode='logical_batch_chunks_v1',atom_bucket_width=16,max_graphs_per_chunk=32,
                      max_padded_cost_per_chunk=1000000)) and refs['A5_execution']['sha256']==EXEC_SHA,
         'Original manual A5 execution required; no auto profile or algorithm change')
    need(anchor['seed']==0 and anchor['input']=='native_s' and anchor['smoke'] is False
         and anchor['data_version']['sampler']['max_padded_cost']==8000000
         and anchor['data_version']['sampler']['padded_cost_multiplier']==3
         and anchor['data_version']['loader']['num_workers']==8
         and anchor['original_shard_snapshot_prejob_sha256']==refs['S_original_snapshot']['sha256'],
         'Historical data/options anchor differs; its old code is not new qualification')
    return dict(refs=refs,anchor=anchor,CPU=refs['full_CPU_Root_closure'],
                source_count=len(before['runtime']['project_source_sha256']),
                external_source_count=len(before['runtime']['external_source_refs']))

def audit_fixed_gate(gate,rule):
    need(gate['gate']=='A_fixed_batch_equivalence' and gate['batches']==20
         and gate['acceptance_rules']==rule and len(gate['results'])==20,'Original full fixed20 required')
    need(rule['version']=='v2' and rule['fixed_batch_only'] is False
         and rule['semantic_contract_sha256']==canonical(rule['semantic_contract']),'Versioned v2 semantic contract differs')
    contract=rule['semantic_contract']
    need(contract['elementwise']==dict(atol=1e-8,rtol=1e-4,formula='abs(a-b)<=atol+rtol*abs(b)',all_elements=True)
         and contract['analytic_zero']['both_L2_norm_max']==1e-8,'User-approved v2 thresholds differ')
    proofs=rule['analytic_zero_parameter_proofs']
    for rows in proofs.values():
        need(len(rows)==6 and {r['name'] for r in rows}==ZERO
             and all(r['shape']==[8] and r['heads']==8 and r['dimension']==512
             and r['parameter_identity_checked'] is True for r in rows),'Actual complete six per-head analytic-zero proofs required')
    need(set(proofs)=={'reference','candidate'},'Both actual model proof sets required')
    names=forward_names=None;passed=True;max_forward=max_ratio=max_abs=max_zero=0.;disabled=0
    for index,batch in enumerate(gate['results']):
        need(batch['batch']==index,'Exact original fixed batch order differs')
        f,g=batch['forward'],batch['gradient'];fs=f['tensors'];gs=g['tensors']
        current={r['name'] for r in gs};fn={r['name'] for r in fs}
        need(len(gs)==len(current)==329 and len(fs)==len(fn)==8
             and (names is None or names==current) and (forward_names is None or forward_names==fn),
             'All329 named parameters and all8 outputs must be retained in every batch')
        names,forward_names=current,fn;fp=gp=True
        need(f['tolerance']==1e-5 and g['atol']==1e-8 and g['rtol']==1e-4
             and g['zero_norm_tolerance']==1e-8 and g['acceptance_version']=='v2'
             and g['semantic_contract_sha256']==rule['semantic_contract_sha256']
             and len(g['analytic_zero_names'])==6 and set(g['analytic_zero_names'])==ZERO,'Actual gate version/tolerances differ')
        for row in fs:
            value=number(row['relative_l2']);max_forward=max(max_forward,value)
            ok=value<=1e-5;need(row['pass'] is ok,'Output pass differs from original relative gate');fp=fp and ok
        for row in gs:
            zero=row['name'] in ZERO;need(row['analytic_zero'] is zero,'Analytic-zero declaration is not actual parameter identity')
            if row.get('reason')=='both_disabled':
                need(not zero and row['reference_shape'] is None and row['candidate_shape'] is None
                     and row['reference_norm'] is None and row['candidate_norm'] is None
                     and row['pass'] is True,'Only both-None inactive parameters are legal')
                disabled+=1;continue
            need(row['reference_shape']==row['candidate_shape']==row['shape']
                 and row['finite'] is True and type(row['elements']) is int and row['elements']>=0
                 and math.prod(row['shape'])==row['elements'],'Actual finite same-shape gradients required')
            nr,nc,nd=(number(row[k]) for k in ('reference_norm','candidate_norm','difference_norm'))
            count=row['violating_elements'];need(type(count) is int and 0<=count<=row['elements'],'Element violation count required')
            absolute=number(row['max_absolute']);lo=number(row['minimum_combined_threshold']);hi=number(row['maximum_combined_threshold'])
            ratio=number(row['maximum_error_to_threshold'])
            need(lo<=hi and (lo>=1e-8 or row['elements']==0) and row['zero_threshold_failure'] is False,'Finite exact combined threshold audit required')
            element_pass=count==0 and ratio<=1
            zero_pass=not zero or (nr<=1e-8 and nc<=1e-8);ok=element_pass and zero_pass
            need(row['elementwise_pass'] is element_pass and row['pass'] is ok
                 and row['analytic_zero_norm_pass']==(zero_pass if zero else None),'Per-element/zero-norm reported decision differs')
            max_ratio=max(max_ratio,ratio);max_abs=max(max_abs,absolute)
            if zero:max_zero=max(max_zero,nr,nc)
            gp=gp and ok
        need(f['pass'] is fp and g['pass'] is gp and batch['pass'] is (fp and gp),'Batch aggregate differs')
        passed=passed and fp and gp
    need(gate['pass'] is passed,'Fixed gate aggregate differs')
    return dict(passed=passed,batches=20,parameters_each=329,outputs_each=8,both_disabled_records=disabled,
                maximum_forward_relative_l2=max_forward,maximum_error_to_threshold=max_ratio,
                maximum_gradient_absolute=max_abs,maximum_analytic_zero_norm=max_zero)

def close(args):
    need(os.getuid()==1278,'Root account required')
    package=verify_package(args.source_pins_sha256);qualified=validate_sources()
    submission,sref=read(CONTROL/'Root_submission_actual_v1.json')
    need(submission['schema']=='model_v3_A5_R2_Root_single_submission_v2'
         and submission['status']=='SUBMITTED' and submission['job_id']==args.job_id
         and submission['source_package']==package,'Actual new family submission/package required')
    verify_method(submission['operations_publication'])
    observed={k:reference(path) for k,path in dict(configuration=OUT/'configuration.json',
        run_status=OUT/'run_status.json',supervisor=FAMILY/'supervisor.json').items()}
    cfg,status,sup=(bound(observed[k]) for k in ('configuration','run_status','supervisor'))
    need(cfg['job_id']==args.job_id and cfg['code_sha']==CODE and cfg['prereg_sha']==PUBLIC
         and cfg['gpu_uuid']==GPU and cfg['node'].split('.')[0]==NODE and cfg['input']=='native_s'
         and cfg['seed']==0 and cfg['smoke'] is False and cfg['fixed_batches']==20 and cfg['trajectory_updates']==500
         and cfg['model']==qualified['anchor']['model'] and cfg['candidate']==qualified['anchor']['candidate']
         and cfg['reference']==qualified['anchor']['reference'] and cfg['optimizer']==qualified['anchor']['optimizer']
         and cfg['loss_policy']==qualified['anchor']['loss_policy'] and cfg['loss_weights']==qualified['anchor']['loss_weights']
         and cfg['supervision']==qualified['anchor']['supervision'],'Original model/options/loss/optimizer/seed scope differs')
    need(cfg['data_version']['sampler']['max_padded_cost']==8000000
         and cfg['data_version']['sampler']['padded_cost_multiplier']==3 and cfg['data_version']['loader']['num_workers']==8
         and cfg['original_shard_snapshot_prejob_sha256']==qualified['refs']['S_original_snapshot']['sha256']
         and cfg['candidate_options_sha256']==qualified['refs']['candidate_options']['sha256']
         and cfg['performance_execution_request']==qualified['refs']['A5_execution'],'Original fixed data/execution rawrefs differ')
    execution=cfg['performance_execution'];need(execution['requested']['checkpoint_policy']=='manual'
         and execution['requested']['capacity_profile'] is None and execution['requested']['resident_models']==2
         and execution['selection'] is None and execution['resolved_options']==cfg['candidate'],'No auto/profile or other resolved-option substitution')
    for name,digest in cfg['source_sha256'].items():
        path=Path(name);need(not path.is_absolute() and '..' not in path.parts,'Relative execution source required')
        need(reference(W/path)['sha256']==digest,'Actual run source differs from current tested code')
    need(canonical({k:v for k,v in cfg.items() if k!='configuration_sha256'})==cfg['configuration_sha256'],
         'Actual canonical saved configuration SHA differs')
    storage,storage_ref=read(FAMILY/'supervisor.json.storage.json')
    need(storage['schema']=='model_v3_private_storage_v1' and str(storage['job_id'])==args.job_id
         and storage['uid']==1278 and sup['private_storage_bindings_path']==storage_ref['path']
         and cfg['private_storage_bindings']['receipt_path']==storage_ref['path']
         and cfg['private_storage_bindings']['receipt_sha256']==storage_ref['sha256'],
         'Actual supervisor/child private receipt identity differs')
    rule=cfg['acceptance_rules'];need(cfg['acceptance_scope']=='V2_FULL20_AND500'
         and rule['rule_publication']==qualified['refs']['rule_publication']
         and rule['rule_document']==qualified['refs']['rule_document'],'Exact actual public rule binding required')
    gate,gref=read(OUT/'fixed_batch_gate.json',16<<20)
    need(gref==dict(path=str(OUT/'fixed_batch_gate.json'),bytes=6242166,
         sha256='478ea13adfd591ef61b644d62c522a597048592e07cebe49a3d6e5f4daf8f042'),
         'Exact preserved4704 original fixed-gate rawref required')
    fixed=audit_fixed_gate(gate,rule)
    raw_argv=['sacct','-X','-n','-P','-j',args.job_id,'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
    result=subprocess.run(raw_argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45,check=False)
    account=dict(argv=raw_argv,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
    row=parent(account,args.job_id,node=NODE,positive=False)
    need(0<int(row[4])<=7200,'Actual original two-hour bound differs')
    c0=row[2:4]==['COMPLETED','0:0']
    need(str(sup['job_id'])==args.job_id and sup['supervisor_source_sha256']==reference(W/'tools/model_v3/run_supervised.py')['sha256']
         and sup['launch_identity']['uid']==1278 and sup['launch_identity']['argv']==sup['command']
         and sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[],
         'Actual source/UID/argv/process/private closure differs')
    command=sup['command'];need(command[:4]==[cfg['logical_python'],'-u','-B','tools/model_v3/paired_a_acceptance.py'],'Original actual paired entry required')
    def arg(name):
        need(command.count(name)==1 and command.index(name)+1<len(command),'Exactly one actual CLI argument required: '+name)
        return command[command.index(name)+1]
    need(arg('--code-sha')==CODE and arg('--prereg-sha')==PUBLIC and arg('--acceptance-version')=='v2'
         and arg('--acceptance-prereg-sha')==RULE_PUBLIC and '--fixed-batch-only' not in command
         and arg('--performance-execution-sha256')==EXEC_SHA
         and arg('--acceptance-rule-document')==qualified['refs']['rule_document']['path']
         and arg('--acceptance-rule-document-sha256')==qualified['refs']['rule_document']['sha256']
         and arg('--acceptance-rule-publication')==qualified['refs']['rule_publication']['path']
         and arg('--acceptance-rule-publication-sha256')==qualified['refs']['rule_publication']['sha256']
         and arg('--input')=='native_s'
         and arg('--seed')=='0' and arg('--workers')=='8' and arg('--max-padded-cost')=='8000000'
         and '--deterministic-controls' in command,'Actual original full20/500/v2 CLI differs')
    need(status['failure'] is None and status['cleanup_errors']==[]
         and status['stream_cleanup']['input_descriptors_closed'] is True and status['stream_cleanup']['errors']==[]
         and status['acceptance_rules']==rule and status['acceptance_scope']=='V2_FULL20_AND500',
         'Actual trainer/SDK/stream cleanup or full scope differs')
    # Original sampled resource journal: same strict unknown rejection and85% limit.
    resource,rref=read_resource_metadata()
    private=sup['private_storage_final']
    need(private['budget_bytes']==LIMIT and private['first_sampling_failure'] is None
         and number(private['sampled_max_bytes'])<=LIMIT and number(sup['last_output_bytes'])<=LIMIT
         and number(sup['elapsed_seconds'])<=6900 and sup['output_budget_bytes']==LIMIT
         and sup['child_output_budget_bytes']==LIMIT-(96<<20),'Original private/output/wall/child-ceiling bounds differ')
    spec=importlib.util.spec_from_file_location('A5_v2_stat_only_monitor',W/'tools/model_v3/runtime_monitor.py')
    monitor=importlib.util.module_from_spec(spec);spec.loader.exec_module(monitor)
    whole=monitor.owned_output_bytes(OUT)+monitor.owned_output_bytes(CONTROL)
    for path in FAMILY.iterdir():
        if path in (OUT,CONTROL):continue
        entry=path.lstat()
        need(stat.S_ISREG(entry.st_mode) and entry.st_uid==1278 and entry.st_nlink==1,
             'Owned ordinary top-level management output required')
        whole+=entry.st_size  # stat only: original supervisor journal can exceed2MiB
    need(whole<=LIMIT,'Disjoint child/control/management whole-family2GiB exceeded')
    summary_ref=trajectory_ref=None;trajectory_ok=False
    if fixed['passed']:
        summary,summary_ref=read(OUT/'summary.json');trajectory,trajectory_ref=read(OUT/'trajectory_gate.json')
        need(trajectory['gate']=='A_500_update_loss_trajectory' and trajectory['updates']==500
             and len(trajectory['results'])==500,'Original complete500 trajectory required')
        for index,item in enumerate(trajectory['results'],1):
            need(item['step']==index and type(item['pass']) is bool,'Exact500 loss point order required')
            ok=number(item['relative_difference'])<=1e-3
            need(item['pass'] is ok,'Original per-point loss decision differs')
        trajectory_ok=all(item['pass'] for item in trajectory['results'])
        need(trajectory['pass'] is trajectory_ok and summary['trajectory_pass'] is trajectory_ok
             and summary['fixed_batch_pass'] is True and summary['full_A_numeric_acceptance'] is trajectory_ok
             and summary['code_sha']==CODE and summary['gpu_uuid']==GPU and summary['configuration_sha256']==cfg['configuration_sha256']
             and summary['acceptance_rules']==rule and summary['acceptance_scope']=='V2_FULL20_AND500'
             and status['committed_trajectory_updates']==500 and status['trajectory_completed'] is True,'Actual full500 summary/committed cursor differs')
    else:
        need(status['status']=='FIXED_BATCH_GATE_FAILED' and status['trajectory_started'] is False
             and status['committed_trajectory_updates']==0 and status['trajectory_completed'] is False and not c0,
             'Failed20 may not claim500 or parent C0')
    passed=c0 and fixed['passed'] and trajectory_ok
    if passed:need(sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
                   and status['status']=='PAIRED_GATES_PASS','Actual positive parent/child supervision differs')
    return dict(schema='model_v3_A5_R2_v2_posthoc_Root_metadata_closure_v2',
        status='ACTUAL_GPU_C0_A5_V2_FULL20_500_SOURCE_RESOURCE_CLOSED' if passed else 'ACTUAL_TERMINAL_A5_V2_NUMERIC_NEGATIVE_PRESERVED',
                job_id=args.job_id,actual_sacct=account,source_package=package,source_qualification=qualified['CPU'],
        consumer_source=reference(Path(__file__).absolute()),
        posthoc_metadata_adaptation=dict(original_consumer_sha256='aca6b4fba63e484eb6222d06a2d0ed75e01fb89ed1c61b018ded354bdd2094ea',
            fixed_batch_index_base=0,resource_fixed_batch_index_base=0,trajectory_index_base=1,
            model_rule_parameter_or_GPU_execution_changed=False,original_rejection_retained=True),
        submission=sref,operations_publication=submission['operations_publication'],artifact_refs=observed,
        fixed_batch_gate=gref,fixed_gate_metadata_cap_bytes=16<<20,summary=summary_ref,trajectory_gate=trajectory_ref,
        fixed20=fixed,trajectory500_passed=trajectory_ok,full_A_numeric_acceptance=passed,resident_models=2,
        original_manual_policy=True,auto_R1_ABBA_or_universal_capacity_acceptance=False,
        resources=resource,resources_rawref=rref,whole_family_bytes=whole,
        SDK_payload_read_or_independent_audit_claimed=False,no_retry_or_registry_release=True)

def read_resource_metadata():
    path=OUT/'resources.jsonl';ref=reference(path);rows=[]
    with path.open() as stream:
        for line in stream:
            need(len(line)<=1<<20 and line.endswith('\n'),'Complete bounded resource metadata row required')
            rows.append(json.loads(line))
    need(reference(path)==ref,'Resource metadata changed')
    fixed=[r['batch'] for r in rows if r['phase']=='fixed_batch']
    trajectory=[r['optimizer_updates'] for r in rows if r['phase']=='trajectory']
    need(fixed==list(range(20)) and (trajectory==[] or trajectory==list(range(1,501))),'Actual resource phase/count coverage differs')
    maximum=0
    for row in rows:
        need(row['foreign_gpu_risk_observed'] is False,'Foreign GPU risk observed')
        gpu=row['gpu_observation'];need(gpu['uuid']==GPU and type(gpu['total_bytes']) is int and gpu['total_bytes']>0,'Known actual GPU total/UUID required')
        own=0
        for process in gpu['compute_processes']:
            need(type(process['own']) is bool and type(process['used_memory_bytes']) is int and process['used_memory_bytes']>=0,'Unknown GPU ownership/memory is not zero')
            need(process['own'] is True,'Foreign selected-GPU process observed');own+=process['used_memory_bytes']
        peak=max(own,number(row['peak_allocated_bytes']),number(row['peak_reserved_bytes']))
        need(peak<=.85*gpu['total_bytes'] and number(row['process_rss_sum_bytes'])<=RSS
             and number(row['output_bytes'])<=LIMIT,'Original85%/RSS56GiB/output2GiB exceeded')
        maximum=max(maximum,peak)
    return dict(rows=len(rows),fixed_batches=20,trajectory_updates=len(trajectory),sampled_GPU_peak_bytes=maximum),ref

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-pins-sha256',required=True);parser.add_argument('--job-id',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    need(args.job_id=='4524704' and args.output.absolute()==CONTROL/'Root_closure_actual_v2.json' and not args.output.exists(),'Fresh explicit control closure output required')
    try:value=close(args);rc=0 if value['full_A_numeric_acceptance'] else 1
    except BaseException as error:
        value=dict(schema='model_v3_A5_R2_v2_posthoc_Root_metadata_rejection_v2',status='REJECTED_OR_INCOMPLETE_PRESERVED',
                   job_id=args.job_id,consumer_source=reference(Path(__file__).absolute()),error=dict(type=type(error).__name__,message=str(error)),full_A_numeric_acceptance=False)
        rc=1
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();need(len(raw)<=META,'Closure metadata cap')
    with args.output.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    print(json.dumps(dict(output=reference(args.output),status=value['status'])));return rc

if __name__=='__main__':raise SystemExit(main())
