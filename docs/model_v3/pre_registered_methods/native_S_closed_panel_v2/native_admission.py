"""Native-only metadata admission; no checkpoint deserialization or registration."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

B=Path('/share/home/zixiao/descriptor_analysis')
N=B/'runs/model_v3_20261026'
REGISTRY=N/'native_S_profile_registered_reservations_v6.json'
NATIVE_PHASE=N/'native_S_B20k_v3'
PANEL_SHA='39cf4929299cd227a3c361183a4b26c8b1405900'
LIMIT=2*1024**3
FIVE={'current/phychem_mfm/phase1/v3_encoder_bridge.py',
      'current/phychem_mfm/phase1/v3_native_checkpoint_bridge.py',
      'tools/model_v3/evaluate_dev_panel.py','current/tests/test_model_v3_native_checkpoint_bridge.py',
      'docs/model_v3/NATIVE_CHECKPOINT_DEV_PANEL_V1.md'}

def need(ok,reason):
    if not ok:raise ValueError(reason)
def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()
def binding(path,limit=512*1024**2):
    path=Path(path).absolute();before=path.lstat()
    need(path.is_file() and not path.is_symlink() and before.st_uid==os.getuid() and before.st_nlink==1
         and before.st_size<=limit,'Owned ordinary bounded file required: '+str(path))
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    after=path.stat()
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
         (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Input changed while hashing')
    return {'path':str(path),'bytes':before.st_size,'sha256':h.hexdigest()}
def bare(ref):
    need(isinstance(ref,dict) and all(ref.get(k) is not None for k in ('path','bytes','sha256')),'Actual rawref is missing/unbound')
    return {k:ref[k] for k in ('path','bytes','sha256')}
def read_ref(ref,limit=2*1024**2):
    value=bare(ref);need(binding(value['path'],limit)==value,'Bound metadata changed')
    return json.loads(Path(value['path']).read_bytes())
def same_reference(candidate,authority,*,state_key=None):
    need(candidate['path']==authority['path'] and candidate['sha256']==authority['sha256'],'Reference path/SHA differs')
    if 'bytes' in candidate:need(candidate['bytes']==authority['bytes'],'Reference bytes differ')
    if state_key is not None:need(candidate.get('state_key')==state_key,'Typed state key differs')
    need(binding(authority['path'])==bare(authority),'Current authority bytes changed')
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

def terminal(ref,job):
    record=read_ref(ref)
    native_projection=False
    if 'raw_sacct' in record:
        need(record.get('schema')=='native_S_actual_terminal_projection_v2'
             and record.get('job_id')==job and record.get('status')=='COMPLETED'
             and record.get('exit_code_raw')=='0:0'
             and type(record.get('exit_code')) is int and record['exit_code']==0,
             'Actual typed Native terminal projection is not C0')
        record=read_ref(record['raw_sacct'])
        native_projection=True
    need(type(record.get('returncode')) is int and record['returncode']==0
         and isinstance(record.get('stdout'),str),'Actual successful sacct observation required')
    if 'stdout_sha256' in record:
        need(record['stdout_sha256']==hashlib.sha256(record['stdout'].encode()).hexdigest(),
             'Raw sacct stdout SHA differs')
    else:
        # The actual v2 producer binds the complete raw JSON by bytes/SHA. Its
        # known six-key raw record has no additional stdout_sha256 property.
        need(native_projection and set(record)=={
             'argv','started_unix','completed_unix','returncode','stdout','stderr'}
             and record['argv']==['sacct','-X','-n','-P','-j',job,
                                   '--format=JobIDRaw,State,ExitCode']
             and record['stderr']=='' and record['stdout']==job+'|COMPLETED|0:0\n'
             and all(type(record[k]) in (int,float) and 0<=record[k]<1e20
                     for k in ('started_unix','completed_unix'))
             and record['started_unix']<=record['completed_unix'],
             'Missing stdout checksum is supported only for exact bound Native-v2 raw accounting')
    argv=record['argv'];need(argv[0]=='sacct' and '-j' in argv and argv[argv.index('-j')+1]==job,'Actual sacct job differs')
    format_token=next((item for item in argv if item.startswith('--format=')),None)
    need(format_token is not None,'Explicit actual sacct columns required')
    names=format_token.split('=',1)[1].split(',')
    rows=[dict(zip(names,line.split('|'))) for line in record['stdout'].splitlines() if line.strip()]
    parents=[row for row in rows if row.get('JobIDRaw',row.get('JobID'))==job]
    need(len(parents)==1 and parents[0].get('State')=='COMPLETED'
         and parents[0].get('ExitCode')=='0:0','Actual parent C0 required')
    if 'User' in names:need(parents[0]['User']=='zixiao','Actual parent owner differs')
    if 'AllocCPUS' in names:need(int(parents[0]['AllocCPUS'])>=16,'Actual parent CPU allocation differs')
    return parents[0]

def supervisor(ref,job,*,kind):
    value=read_ref(ref);validate_supervisor_record(value,job,kind=kind);return value

def validate_supervisor_record(value,job,*,kind):
    need(str(value['job_id'])==job and value['status']=='COMPLETED' and value['exit_code']==0
         and value['first_failure'] is None,'Actual supervisor did not close C0')
    if kind=='CPU':
        need(value['remaining']==[] and value['private_storage']['first_sampling_failure'] is None,
             'CPU supervisor remaining/private-storage closure failed')
        need(value['launch_identity']['uid']==1278 and value['gpu_initialization_permitted'] is False,
             'CPU supervisor UID/CUDA policy differs')
    elif kind=='GPU':
        need(value['remaining_recorded_processes_before_retirement']==[] and value['private_storage_cleanup_errors']==[],
             'GPU supervisor process/private cleanup failed')
    else:raise ValueError('Explicit CPU or GPU supervisor kind required')
    return value

def git_identity(root,code,tree):
    executable=B/'runs/model_v3_20261025/cpu_git_tools_v1/bin/git'
    def call(*args):
        result=subprocess.run([str(executable),'-C',str(root),*args],stdin=subprocess.DEVNULL,
                              capture_output=True,text=True,timeout=30)
        need(result.returncode==0,'Actual fixed Git metadata call failed')
        return result.stdout.strip()
    need(call('rev-parse','HEAD')==code and call('rev-parse','HEAD^{tree}')==tree,
         'Current local HEAD/tree differs from tested published bridge')
    need(call('status','--porcelain','--untracked-files=all')=='','Tested bridge tree must remain completely clean')
    return {'HEAD':code,'tree':tree,'porcelain':'','git_executable':binding(executable,16*1024**2)}

def independent_root(path,repository):
    path=Path(path).absolute()
    real=path.resolve();n=N.resolve();phase=NATIVE_PHASE.resolve();repo=Path(repository).resolve()
    need(real.is_relative_to(n) and real!=n and not real.is_relative_to(phase) and not real.is_relative_to(repo),
         'Independent actual N root required, outside Native phase and repository')
    for ancestor in (path,*path.parents):
        if ancestor.exists() or ancestor.is_symlink():
            info=ancestor.lstat()
            need(stat.S_ISDIR(info.st_mode) and not ancestor.is_symlink(),'Output ancestor must be a real ordinary directory')
            if ancestor==N:break
    need(real==path,'No output ancestor aliases or symlinks allowed')
    return real

def bridge_admission(value):
    root=Path(value['repository_root']).absolute();qa=read_ref(value['CPU_Root_closure'],16*1024**2)
    need(qa['schema']=='model_v3_native_checkpoint_bridge_CPU_Root_closure_v1'
         and qa['status']=='ACTUAL_C0_FOUR_RELATED_GROUPS_AND_REPOSITORY_CHECKER','Actual bridge CPU Root closure required')
    summary=read_ref(qa['unit_summary'],16*1024**2);job=str(summary['job_id'])
    raw=qa['actual_parent'];need(raw['returncode']==0 and raw.get('stderr','')=='','Actual CPU parent capture failed')
    argv=raw['argv'];need(argv[0]=='sacct' and '-j' in argv and argv[argv.index('-j')+1]==job,'CPU parent job differs')
    fmt=next((x.split('=',1)[1].split(',') for x in argv if x.startswith('--format=')),None)
    need(fmt is not None,'Explicit CPU parent columns required')
    rows=[dict(zip(fmt,line.split('|'))) for line in raw['stdout'].splitlines() if line.strip()]
    parents=[r for r in rows if r.get('JobIDRaw',r.get('JobID'))==job]
    need(len(parents)==1 and parents[0]['User']=='zixiao' and parents[0]['State']=='COMPLETED'
         and parents[0]['ExitCode']=='0:0' and int(parents[0]['AllocCPUS'])==16
         and re.fullmatch(r'compute-0-(?:2|[89]|1[0-9])',parents[0]['NodeList']),'Actual CPU C0/UID/node/16CPU required')
    supervisor(qa['supervisor'],job,kind='CPU')
    checker=read_ref(qa['repository_checker']);need(checker.get('status')=='PASS' and checker.get('errors')==[],
                                                  'Actual repository checker PASS required')
    request=read_ref(qa['unit_request'],16*1024**2)
    need(summary['status']=='PASS' and summary['cuda_visible_devices']=='' and int(summary['requested_cpus'])==16
         and summary['request_sha256']==qa['unit_request']['sha256'],'Actual CPU summary/request differs')
    names={'native_checkpoint_bridge','old_encoder_bridge','old_architecture_training','H0_runtime_and_dev_evaluation'}
    need({r['name'] for r in summary['units']}=={r['name'] for r in request['tasks']}==names,'All four related groups required')
    for task in summary['units']:
        planned=next(r for r in request['tasks'] if r['name']==task['name'])
        need(task['returncode']==0 and task['sources_unchanged'] and task['source_hashes_before']==task['source_hashes_after']==planned['sources'],
             'Actual related QA/source closure failed')
        xml=Path(qa['unit_summary']['path']).parent/(task['name']+'.xml');binding(xml,16*1024**2)
        counts={k:0 for k in ('tests','failures','errors','skipped')}
        for suite in ET.parse(xml).getroot().iter('testsuite'):
            for key in counts:counts[key]+=int(suite.attrib.get(key,0))
        need(counts==task['counts'] and counts['tests']>0 and counts['failures']==counts['errors']==counts['skipped']==0,
             'Actual selected four JUnit groups require zero failures/errors/skips')
    whole_inventory={}
    for task in summary['units']:
        for path,sha in task['source_hashes_before'].items():
            need(path not in whole_inventory or whole_inventory[path]==sha,'Conflicting whole QA source maps')
            whole_inventory[path]=sha
    need(whole_inventory,'Complete QA source map is empty')
    for path,sha in whole_inventory.items():
        need(binding(path,16*1024**2)['sha256']==sha,'Untested current source change: '+path)
    freeze=read_ref(qa['source_freeze']);need({r['file'] for r in freeze['files']}==FIVE,'Tested-five freeze required')
    refs={r['file']:binding(root/r['file'],2*1024**2) for r in freeze['files']}
    authored={Path(r['path']).absolute():bare(r) for r in qa['authored_files']}
    native=next(r for r in summary['units'] if r['name']=='native_checkpoint_bridge')
    need(str(root/'current/tests/test_model_v3_native_checkpoint_bridge.py') in native['argv'],'Whole Native bridge test module required')
    for item in freeze['files']:
        ref=refs[item['file']]
        need(ref['sha256']==item['sha256'] and ref['bytes']==item['bytes']
             and native['source_hashes_before'].get(ref['path'])==ref['sha256']
             and authored.get(Path(ref['path']))==ref,'Tested five source bytes changed')
    publication=read_ref(value['publication'])
    need(publication['schema']=='model_v3_Root_exact_tree_publication_receipt_v1'
         and publication['status'].startswith('PUBLISHED_'),'Actual Root exact-tree publication receipt required')
    code,public,tree=(publication[k] for k in ('local_code_sha','public_commit_sha','tree_sha'))
    need(all(re.fullmatch('[0-9a-f]{40}',x) for x in (code,public,tree)),'Actual local/public/tree identity required')
    actual_git=git_identity(root,code,tree)
    branch=publication['branch'];rb=publication['actual_readback']
    need(rb.get(branch,rb.get(branch.replace('-','_')))==public,'Actual published branch readback differs')
    published={r['path']:r for r in publication['source_files']}
    for rel,ref in refs.items():
        row=published.get(rel);need(row is not None and row['sha256']==ref['sha256'] and row['bytes']==ref['bytes'],
                                   'Tested source missing/different in public tree')
        raw=Path(ref['path']).read_bytes()
        need(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==row['blob_sha'],'Public Git blob differs')
    return {'repository_root':str(root),'evaluation_code_sha':code,'public_code_sha':public,'tree_sha':tree,
        'tested_sources':refs,'qa_job_id':job,'qa_counts':{r['name']:r['counts'] for r in summary['units']},
        'source_inventory':whole_inventory,'actual_git':actual_git,'validation_inputs':value}
def native_admission(value):
    member_ref,complete_ref,payload_ref=(bare(value[k]) for k in ('member_result','completion','payload'))
    member,marker=read_ref(member_ref),read_ref(complete_ref)
    need(member['schema']=='existing_native_S_precision_member_v1' and member['status'] in
         ('SEGMENT_PAUSED','UPDATES_COMPLETE_PENDING_OUTER_TERMINAL'),'Closed Native member metadata required')
    contract=member['member_contract']
    need(member['scope']==contract['source_scope']=='existing_native_S_original_TRAIN_record_sampler_not_D5'
         and member['D5_authority'] is False and member['scientific_acceptance'] is False and contract['D5_authority'] is False,
         'Native descriptive scope only')
    need(type(member['seed']) is int and member['seed'] in (0,1) and member['seed']==contract['seed']
         and member['precision'] in ('fp32','bf16') and member['precision']==contract['precision'],'Native member seed/precision mismatch')
    need(marker['schema']=='model_v3_training_checkpoint_v1' and marker['payload_bytes']==payload_ref['bytes']
         and marker['payload_sha256']==payload_ref['sha256'],'Typed COMPLETE/payload authority differs')
    need(Path(complete_ref['path']).name=='COMPLETE.json' and Path(payload_ref['path']).name=='payload.pt'
         and Path(complete_ref['path']).parent==Path(payload_ref['path']).parent,'Immutable COMPLETE/payload directory required')
    for key in ('optimizer_updates','samples_consumed'):
        need(type(member[key]) is int and member[key]>0 and member[key]==marker[key],'Native closed header/member cursor differs')
    need(member['optimizer_updates']<=contract['plan']['updates'],'Native endpoint exceeds unchanged plan')
    expected={'code_sha':contract['code_sha'],'configuration_sha256':canonical(contract),
        'registry_sha256':contract['source_files']['current/phychem_mfm/phase1/v3_native_s_precision_data.py'],'normalization_sha256':canonical({}),
        'data_version':contract['data_version'],'source_inventory_sha256':canonical(contract['source_files'])}
    # registry source key is producer-owned; compare to member contract rather than invented labels.
    need(marker['bindings']==expected,'Native COMPLETE/source/data/config bindings differ')
    closure=read_ref(value['segment_closure']);submission=read_ref(closure['submission'])
    need(closure['schema']=='native_S_long_segment_Root_closure_v1'
         and closure['status']=='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING' and closure['failure'] is None
         and closure['member_result']==member_ref and closure['checkpoint_directory']==str(Path(complete_ref['path']).parent)
         and closure['optimizer_updates']==member['optimizer_updates'],'Actual successful producing segment/endpoint required')
    job=str(submission['actual_sbatch_job_id']);terminal(closure['actual_terminal'],job);supervisor(closure['supervisor'],job,kind='GPU')
    need(submission['seed']==member['seed'] and submission['precision']==member['precision']
         and submission['start_update']<member['optimizer_updates']<=submission['target_update'],'Actual producing member range differs')
    need(binding(payload_ref['path'])==payload_ref,'Current opaque Native payload SHA/size differs')
    return {'checkpoint':{**payload_ref,'state_key':'model'},'configuration':member_ref,'completion':complete_ref,
        'producer_code_sha':contract['code_sha'],'seed':member['seed'],'precision':member['precision'],
        'optimizer_updates':member['optimizer_updates'],'samples_consumed':member['samples_consumed'],
        'training_phase':submission['phase'],'contract_sha256':canonical(contract),'native_inputs':value}

def storage_admission(value,output_base,*,quota_free_bytes=None,current_output_bytes=0):
    need(Path(value['registry_path']).absolute()==REGISTRY,'Use existing live Root registry')
    registry=json.loads(REGISTRY.read_bytes())
    need(registry['schema']=='native_S_Root_registered_reservations_v1' and registry['authority']=='ROOT_ACTUAL'
         and registry['uid']==os.getuid(),'Actual Root registered reservation table required')
    entry=registry['reservations'].get(value['reservation_id']);need(isinstance(entry,dict),'Panel hold is not actually registered')
    need(Path(entry['phase']).resolve()==Path(output_base).resolve() and entry['principal']==value['principal']
         and entry['principal_sha256']==value['principal']['sha256'],'Independent panel reservation identity differs')
    principal=read_ref(entry['principal'])
    need(principal['reserved_additional_bytes']==LIMIT,'Independent exact2GiB panel hold required')
    need(int(entry['remaining_bytes'])>=max(0,LIMIT-current_output_bytes),'Actual independent panel hold is insufficient')
    need(all(type(row['remaining_bytes']) is int and row['remaining_bytes']>=0 for row in registry['reservations'].values()),'Unknown/negative live reservation amounts are forbidden')
    remaining=sum(row['remaining_bytes'] for row in registry['reservations'].values())
    if quota_free_bytes is not None:need(quota_free_bytes>=remaining,'Actual account quota does not cover all registered remaining holds')
    return {'reservation_id':value['reservation_id'],'entry_snapshot':entry,'entry_snapshot_sha256':canonical(entry),
        'remaining_registered_bytes':remaining,'principal':value['principal'],'registry_path':str(REGISTRY),
        'whole_live_registry_frozen':False,'registrar_or_existing_hold_modified':False}

def whole_output_bytes(base,monitor):
    # Partition the ONE physical family into disjoint immediate children. The
    # frozen SDK allowlist stays relative to evaluation/, never broadened to
    # accept arbitrary nested links. Cross-subtree hardlinks fail nlink checks.
    base=Path(base)
    for attempt in range(3):
        try:
            before=base.lstat();need(stat.S_ISDIR(before.st_mode) and before.st_uid==os.getuid()
                and not base.is_symlink(),'Owned ordinary output family required')
            seen={(before.st_dev,before.st_ino)};total=before.st_size
            for path in base.iterdir():
                info=path.lstat();key=(info.st_dev,info.st_ino)
                need(info.st_uid==os.getuid() and key not in seen,'Output family alias/owner differs');seen.add(key)
                if stat.S_ISDIR(info.st_mode):total+=monitor.owned_output_bytes(path)
                else:
                    need(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'Family top-level entry must be single-link ordinary file')
                    total+=info.st_size
            after=base.lstat();need((before.st_dev,before.st_ino)==(after.st_dev,after.st_ino),'Output family identity changed')
            return total
        except FileNotFoundError:
            if attempt==2:raise
def metadata_selfcheck():
    # Typed synthetic metadata tests in the real future model job. None is an
    # actual job/publication/checkpoint certificate or independent QA parent.
    positive=0;negative=0
    need(canonical({'b':2,'a':1})==canonical({'a':1,'b':2}),'Canonical order control failed');positive+=1
    for row in (None,{}, {'path':'x','sha256':'0'*64}, {'path':None,'bytes':1,'sha256':'0'*64}):
        try:bare(row)
        except ValueError:negative+=1
        else:raise ValueError('Unbound reference admitted by inline control')
    base={'job_id':'7','status':'COMPLETED','exit_code':0,'first_failure':None}
    cpu={**base,'remaining':[],'private_storage':{'first_sampling_failure':None},
         'launch_identity':{'uid':1278},'gpu_initialization_permitted':False}
    gpu={**base,'remaining_recorded_processes_before_retirement':[],'private_storage_cleanup_errors':[]}
    validate_supervisor_record(cpu,'7',kind='CPU');positive+=1
    validate_supervisor_record(gpu,'7',kind='GPU');positive+=1
    for value,kind in ((cpu,'GPU'),(gpu,'CPU'),({**cpu,'remaining':[{'pid':9}]},'CPU'),
                       ({**gpu,'private_storage_cleanup_errors':['failure']},'GPU')):
        try:validate_supervisor_record(value,'7',kind=kind)
        except (KeyError,ValueError):negative+=1
        else:raise ValueError('Wrong/incomplete supervisor closure admitted by inline control')
    for path in (NATIVE_PHASE/'panel',N,N/'../outside'):
        try:independent_root(path,B/'MFM_model_v3_native_checkpoint_bridge_v1')
        except ValueError:negative+=1
        else:raise ValueError('Forbidden panel output boundary admitted')
    need(positive==3 and negative==11,'Inline metadata control count differs')
    return {'scope':'INLINE_SYNTHETIC_METADATA_ONLY','positive_controls':positive,'negative_controls':negative,
            'actual_QA_or_GPU_claimed':False,'separate_QA_parent_claimed':False}
