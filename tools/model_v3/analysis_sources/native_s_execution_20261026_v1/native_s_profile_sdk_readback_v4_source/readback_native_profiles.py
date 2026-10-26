"""One CPU allocation: original29 metadata QA, then two full offline profile SDKs."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import importlib.metadata
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def require(ok,message):
    if not ok:raise ValueError(message)


def ref(path,cap=4<<20):
    path=Path(path);require(path.is_absolute() and path==path.resolve(strict=True) and '..' not in path.parts,'Physical absolute input required')
    before=path.stat();require(path.is_file() and before.st_uid==os.getuid() and before.st_nlink==1 and before.st_size<=cap,'Bounded owned single-link input required')
    raw=path.read_bytes();after=path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Input changed while reading')
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def bind(value,cap=4<<20):
    require(type(value) is dict and set(value)=={'path','bytes','sha256'} and ref(value['path'],cap)==value,'Raw-byte binding differs')
    return Path(value['path'])


def read(value):
    path=bind(value);raw=path.read_bytes()
    def pairs(items):
        result={}
        for key,item in items:require(key not in result,'Duplicate JSON key');result[key]=item
        return result
    parsed=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON literal')))
    bind(value);return parsed


def load_module(value,name):
    path=bind(value);spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


def write(path,value):
    raw=(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    require(len(raw)<=4<<20,'Compact raw metadata output exceeds4MiB')
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return ref(path)


class Store:
    def read_bound(self,value):return read(value)


def closure(context,graph):
    original=read(context['original_independent_inputs']);root=read(context['Root_profile_closure'])
    require(context['schema']=='native_S_evidence_inputs_v2' and context['role']=='sdk_verifier'
        and original['schema']=='native_S_evidence_inputs_v2' and original['role']=='native_full_SDK_verifier'
        and original['status']=='INPUTS_PREPARED_NOT_VERIFIED','New real sdk_verifier call must reference original unmodified inputs')
    require(context['artifacts']==original['artifacts'] and context['profile_result']==original['profile_result']
        and root['schema']=='native_S_short_profile_Root_closure_v1' and root['status']=='PROFILE_OUTER_C0_SCIENCE_HOLD'
        and root['independent_SDK_inputs']==context['original_independent_inputs']
        and root['actual_terminal']==original['actual_terminal'],'Actual profile/root/input chain differs')
    terminal=graph.terminal(Store(),original['actual_terminal'])
    require(terminal['profile_result']==context['profile_result'],'Actual terminal belongs to another profile')
    supervisor=read(root['supervisor'])
    require(str(supervisor['job_id'])==str(terminal['job_id']) and supervisor['status']=='COMPLETED' and supervisor['exit_code']==0
        and supervisor['first_failure'] is None and supervisor['retirement'] is None
        and supervisor['remaining_recorded_processes_before_retirement']==[] and supervisor['private_storage_cleanup_errors']==[],
        'Actual profile supervisor/process cleanup did not close')
    return original,root,supervisor,terminal


def run_one(call_ref,output,deps,modules):
    started=time.monotonic();deadline=started+180
    framing,kernel,reader,graph=modules;call=read(call_ref);original,root,supervisor,terminal=closure(call,graph)
    profile=read(call['profile_result']);artifacts=call['artifacts'];child=Path(call['profile_result']['path']).parent
    require(profile['SDK_expectations']==artifacts and set(artifacts)=={'sdk','mirror','configuration','summary'},'Exact four expected artifacts required')
    for key,name in (('configuration','SDK_expected_configuration.json'),('summary','SDK_expected_summary.json'),('mirror','history.jsonl')):
        require(artifacts[key]['path']==str(child/name),'Expected metadata path differs')
    require(Path(artifacts['sdk']['path']).is_relative_to(child/'wandb')
        and Path(artifacts['sdk']['path']).name=='run-'+profile['tracker_id']+'.wandb','Exact original native SDK required')
    configuration=read(artifacts['configuration']);summary=read(artifacts['summary']);rows=[]
    with bind(artifacts['mirror'],128<<20).open('rb') as stream:
        for line in stream:
            require(len(rows)<102 and len(line)<=4<<20 and line.endswith(b'\n'),'Mirror is truncated/oversized/excessive')
            rows.append(reader.strict_json(line))
    producer=deps['sources']['short_profile']
    require(configuration['profile_runner_source']=={key:producer[key] for key in ('path','sha256')},'Actual runner path and raw SHA differ')
    require(profile['native_code_sha']==deps['model_code_sha'] and profile['prereg_sha']==deps['model_public_sha']
        and configuration['callback']['runtime']==profile['runtime'],'Actual immutable runtime/source identity differs')
    command=supervisor['command'];require(command.count(producer['path'])==1,'Actual supervisor executed another producer')
    for key,value in (('--precision',profile['precision']),('--updates','20'),('--code-sha',deps['model_code_sha']),('--prereg-sha',deps['model_public_sha'])):
        require(command.count(key)==1 and command[command.index(key)+1]==value,'Actual profile command option differs')
    context=kernel.prepare(profile,configuration,summary,rows,job_id=str(terminal['job_id']),expectations=artifacts)
    member=read(call['member_result'])
    require(call['member_result']['path']==str(child/'member_result.json') and member['schema']=='existing_native_S_precision_member_v1'
        and member['tracker']['id']==profile['tracker_id'] and member['precision']==profile['precision'] and member['seed']==0
        and member['optimizer_updates']==20 and member['samples_consumed']==rows[-1]['row']['samples_consumed']
        and set(member['validation'])=={'0'} and member['scientific_acceptance'] is False and member['D5_authority'] is False,
        'Saved committed member clock/population differs')
    from wandb.proto import wandb_internal_pb2 as pb
    from wandb.sdk.internal.datastore import DataStore
    decoder=deps['decoder'];require(importlib.metadata.version('wandb')==decoder['WandB_version'],'Installed W&B version differs')
    sources={'DataStore':framing.installed_source(inspect.getfile(DataStore)),'Record_module':framing.installed_source(pb.__file__)}
    require(sources['DataStore']['sha256']==decoder['DataStore_expected_sha256']
        and sources['Record_module']['sha256']==decoder['Record_module_expected_sha256'],'Installed native decoder source differs')
    scanner=framing.read_only_scanner(DataStore,importlib.import_module(DataStore.__module__))()
    scanner._deadline=deadline;scanner._record_bytes_limit=4<<20
    all_refs=[call_ref,call['original_independent_inputs'],call['Root_profile_closure'],call['profile_result'],call['member_result'],
        original['actual_terminal'],root['supervisor']]+list(artifacts.values())
    terminal_body=read(original['actual_terminal']);all_refs.append(terminal_body['raw_sacct'])
    for value in all_refs:framing.bind(value,128<<20 if value in (artifacts['sdk'],artifacts['mirror']) else 4<<20,deadline)
    try:
        scanner.open_for_scan(artifacts['sdk']['path']);result=kernel.compare(reader,scanner,pb.Record,context,deadline=deadline)
    finally:scanner.close()
    for value in all_refs:framing.bind(value,128<<20 if value in (artifacts['sdk'],artifacts['mirror']) else 4<<20,deadline)
    for name,value in sources.items():require(framing.installed_source(value['path'])==value,'Decoder changed after readback')
    require(time.monotonic()<=deadline,'Inclusive180-second profile verification bound exceeded')
    output.mkdir(mode=0o700)
    history=write(output/'raw_history_verification.json',result['raw_history_verification'])
    tap=write(output/'raw_config_summary_verification.json',result['raw_config_summary_verification'])
    call_binding=write(output/'raw_history_call_binding.json',dict(schema='native_S_bounded_reader_invocation_v2',
        sdk=artifacts['sdk'],mirror=artifacts['mirror'],result=history,expected_run_id=profile['tracker_id'],expected_exit=0,
        expected_history_rows=len(rows),reader_source=deps['sources']['history_reader']))
    return {'precision':profile['precision'],'run_id':profile['tracker_id'],'input_manifest':call_ref,
        'profile_result':call['profile_result'],'expectations':artifacts,'sdk':artifacts['sdk'],
        'history_reader_source':deps['sources']['history_reader'],'raw_history_verification':history,
        'raw_history_call_binding':call_binding,'raw_config_summary_verification':tap,'decoder_sources':sources,
        'actual_profile_terminal':original['actual_terminal'],'actual_profile_Root_closure':call['Root_profile_closure'],
        'elapsed_seconds':time.monotonic()-started,'is_full_storage_or_future_state_certificate':False,'scientific_acceptance':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',action='append',required=True)
    parser.add_argument('--input-sha256',action='append',required=True);parser.add_argument('--pins-sha256',required=True)
    parser.add_argument('--expected-node',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    require(len(args.input)==len(args.input_sha256)==2 and len(set(args.input))==2,'Exactly fp32 and bf16 call manifests required')
    folder=Path(__file__).absolute().parent;pins_ref=ref(folder/'source_pins_v1.json');require(pins_ref['sha256']==args.pins_sha256,'Own source pins SHA differs')
    pins=read(pins_ref);runtime=[]
    require(pins['schema']=='native_S_profile_SDK_readback_source_pins_v1','Exact readback package pins required')
    for value in pins['files']:
        item={'path':str(folder/value['relative_path']),'bytes':value['bytes'],'sha256':value['sha256']};bind(item);runtime.append(item)
    dep_ref=next(value for value in runtime if Path(value['path']).name=='producer_dependencies.json');deps=read(dep_ref)
    for item in deps['sources'].values():bind(item)
    require(os.environ.get('SLURM_JOB_ID','').isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16
        and os.environ.get('CUDA_VISIBLE_DEVICES','') in ('','-1') and os.uname().nodename==args.expected_node
        and re.fullmatch(r'compute-0-(?:2|[8-9]|1[0-9])',args.expected_node),'Actual CPU-only allocation/node required')
    cgroup=Path('/proc/self/cgroup').read_text();job=os.environ['SLURM_JOB_ID']
    require(re.search(r'(?:^|/)job[_/-]'+re.escape(job)+r'(?:/|$)',cgroup,re.M),'Actual own Slurm cgroup required')
    output=Path(args.output);require(output.is_absolute() and output.parent==output.parent.resolve(strict=True),'Fresh physical output parent required')
    output.mkdir(mode=0o700,exist_ok=False);status='FAILED_RAW_OUTPUTS_PRESERVED';code=1;results=[];failure=None
    try:
        xml=output/'metadata29.xml';log=output/'metadata29.log'
        with log.open('xb') as stream:
            qa=subprocess.run([sys.executable,'-B','-m','pytest','-q','-o','cache_dir='+str(output/'pytest_cache'),
                deps['sources']['kernel_tests']['path'],'--junitxml='+str(xml)],stdout=stream,stderr=subprocess.STDOUT,timeout=120,check=False)
        tree=ET.parse(xml).getroot();suites=[tree] if tree.tag=='testsuite' else list(tree.iter('testsuite'))
        counts={name:sum(int(suite.attrib.get(name,'0')) for suite in suites) for name in ('tests','failures','errors','skipped')}
        require(qa.returncode==0 and counts=={'tests':29,'failures':0,'errors':0,'skipped':0} and log.stat().st_size<=1<<20,'Original29 metadata QA did not pass')
        framing=load_module(deps['sources']['framing_factory'],'profile_readback_framing')
        kernel=load_module(deps['sources']['kernel'],'profile_readback_kernel');reader=load_module(deps['sources']['history_reader'],'profile_readback_v7')
        graph=load_module(deps['sources']['storage_evidence_graph'],'profile_readback_existing_graph')
        for index,(path,sha) in enumerate(zip(args.input,args.input_sha256)):
            value=ref(path);require(value['sha256']==sha,'Actual call input SHA differs')
            results.append(run_one(value,output/str(index),deps,(framing,kernel,reader,graph)))
        require({row['precision'] for row in results}=={'fp32','bf16'} and len({row['run_id'] for row in results})==2,'Distinct paired short-profile logs required')
        for value in runtime+list(deps['sources'].values())+[pins_ref]:bind(value)
        status='FULL_PROFILE_LOG_PAYLOADS_MATCHED_PENDING_CPU_OUTER_C0';code=0
    except Exception as exc:failure={'type':type(exc).__name__,'message':str(exc)[:1200]}
    raw_argv=[value.decode() for value in Path('/proc/self/cmdline').read_bytes().split(b'\0') if value]
    execution=write(output/'raw_execution.json',{'schema':'native_S_actual_SDK_readback_execution_v1','argv':raw_argv,'returncode':code,
        'job_id':job,'uid':os.getuid(),'cgroup':cgroup,'source':ref(__file__),'metadata29_source':deps['sources']['kernel_tests']})
    write(output/'READBACK_RESULT.json',{'schema':'native_S_two_profile_SDK_readback_result_v1','status':status,'failure':failure,
        'profiles':results,'raw_execution':execution,'dependency_rebind':dep_ref,'producer_source':ref(__file__),
        'actual_CPU_terminal_not_self_asserted':True,'full_storage_future_state_or_B_acceptance':False,'scientific_acceptance':False})
    return code


if __name__=='__main__':raise SystemExit(main())
