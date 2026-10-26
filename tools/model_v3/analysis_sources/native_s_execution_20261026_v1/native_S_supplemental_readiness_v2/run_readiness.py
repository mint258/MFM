"""One bounded CPU job: literal-key SDK readback, safe CP inventory, full metadata pressure."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def require(ok,message):
    if not ok: raise ValueError(message)


def ref(path,cap=4<<20):
    path=Path(path)
    require(path.is_absolute() and path==path.resolve(strict=True) and '..' not in path.parts,'Physical absolute file required')
    before=path.stat()
    require(path.is_file() and before.st_uid==os.getuid() and before.st_nlink==1 and before.st_size<=cap,'Bounded owned metadata/source required')
    raw=path.read_bytes();after=path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'File changed during read')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def bind(value):
    require(type(value) is dict and set(value)=={'path','bytes','sha256'} and ref(value['path'])==value,'Raw binding differs')
    return Path(value['path'])


def read(value):
    def pairs(items):
        result={}
        for key,item in items:
            require(key not in result,'Duplicate JSON key');result[key]=item
        return result
    return json.loads(bind(value).read_bytes(),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def write(path,value):
    raw=(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    require(len(raw)<=4<<20,'Compact output only')
    with Path(path).open('xb') as stream: stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return ref(path)


def pressure(request,deps,output,inputs_ref,wall_seconds):
    """Call the frozen complete-root/JSON/byte pressure API, not a sampled projection."""
    require(type(wall_seconds) is int and 60<=wall_seconds<=1200,'Bounded full-pressure wall required')
    started=time.monotonic();deadline=started+wall_seconds-10
    target=request['pressure_target']
    inputs=read(inputs_ref)
    require(inputs['schema']=='native_S_evidence_inputs_v2' and inputs['role']=='accounting_runner'
        and inputs['target']==target,'Actual accounting_runner input/target required')
    require(target==dict(managed_roots=512,metadata_records=32768,metadata_bytes=512<<20,inode_protection_limit=100000),
        'Exact Root full-envelope pressure target required')
    for value in deps['pressure_sources'].values():bind(value)
    sys.path.insert(0,deps['immutable_current'])
    sys.path.insert(0,str(Path(deps['pressure_sources']['accounting_pressure']['path']).parent))
    storage=importlib.import_module('phychem_mfm.phase1.v3_long_run_storage')
    require(Path(storage.__file__).absolute()==Path(deps['pressure_sources']['storage']['path']),'Exact immutable accounting implementation required')
    path=bind(deps['pressure_sources']['accounting_pressure'])
    spec=importlib.util.spec_from_file_location('supplemental_original_full_pressure',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    # The original API fills inode_limit with empty fixtures. Its exact minimal
    # full root/JSON/byte layout is metadata_records + managed_roots + 6 entries.
    # Keep 100000 as the protection ceiling, not a claim to exercise that many.
    minimum_inodes=target['metadata_records']+target['managed_roots']+6
    limits=dict(managed_roots=target['managed_roots'],metadata_records=target['metadata_records'],
        metadata_bytes=target['metadata_bytes'],inode_limit=minimum_inodes)
    def guard():require(time.monotonic()<deadline,'Full pressure cooperative deadline exceeded')
    measurement=module.materialize_and_measure(storage,output/'fixture',limits,guard,maximum_output_bytes=2<<30)
    actual_entries=sum(1 for _ in (output/'fixture').rglob('*'))
    require(actual_entries==measurement['inode_entries'] and actual_entries<=target['inode_protection_limit']
        and measurement['managed_roots']==512 and measurement['metadata_records']==32768
        and measurement['metadata_bytes']==512<<20 and measurement['measurement_passes']==8
        and len(measurement['all_measured_seconds'])==3,'Actual complete pressure fixture/passes differ')
    for value in deps['pressure_sources'].values():bind(value)
    guard()
    measurement.update(schema='native_S_accounting_pressure_v2',status='ACCOUNTING_CHILD_COMPLETED_PENDING_OUTER',
        Root_runtime_pin=inputs['Root_runtime_pin'],scope='existing_native_S_original_TRAIN_record_sampler_not_D5',
        CPU_only=True,CUDA_or_native_record_execution=False,reservation_created_by_this_tool=False,D5_authority=False,
        pressure_target=target,inode_protection_limit=100000,actual_inode_entries=actual_entries,
        inode_limit_fully_exercised=actual_entries==100000,sampled_or_extrapolated=False,
        original_API_source=deps['pressure_sources']['accounting_pressure'],immutable_storage_source=deps['pressure_sources']['storage'],
        actual_producer_source=ref(__file__),actual_inputs=inputs_ref,
        elapsed_seconds_including_fixture=time.monotonic()-started,
        independent_Root_accounting_admission_not_created=True,scientific_acceptance=False)
    return write(output/'accounting_pressure.json',measurement)


def observation(inputs_ref,output):
    """Read saved post-GPU metadata only; no model, SDK, CP payload or new census."""
    inputs=read(inputs_ref);role=inputs['role'];profile_ref=inputs['artifacts']['profile_result']
    require(inputs['schema']=='native_S_evidence_inputs_v2' and role in ('precision_verifier','closed_census'),'Exact existing metadata role required')
    profile=read(profile_ref);root=read(inputs['Root_profile_closure']);terminal=read(root['actual_terminal'])
    require(root['status']=='PROFILE_OUTER_C0_SCIENCE_HOLD' and terminal['status']=='COMPLETED' and terminal['exit_code']==0
        and terminal['profile_result']==profile_ref,'Saved actual GPU closure belongs to another profile')
    if role=='precision_verifier':
        raw=profile['direct_precision_observation']
        require(raw['schema']=='native_S_selective_precision_operator_interfaces_v2' and raw['status']=='OBSERVED_OPERATOR_INTERFACES'
            and raw['actual_device']=='cuda' and set(raw['layers'])==set(map(str,range(6))) and all(raw['coverage'].values()),
            'Actual six-layer saved operator observations required')
        saved=write(output/'operator_observation.json',raw)
    else:
        seal=root['actual_seal'];require(seal['returncode']==0,'Actual Root post-terminal seal failed')
        census=json.loads(seal['stdout'])['current_census'];child=str(Path(profile_ref['path']).parent)
        total=census['directory_bytes'][child];checkpoint=profile['checkpoint_ref']['bytes']
        require(type(total) is int and type(checkpoint) is int and total>=checkpoint,'Actual closed child/checkpoint byte counts differ')
        saved=write(output/'closed_census.json',dict(schema='native_S_actual_closed_census_v2',profile_result=profile_ref,
            child_total_bytes=total,checkpoint_payload_bytes=checkpoint,non_checkpoint_output_bytes=total-checkpoint,
            coverage_observation=profile['coverage_observation'],after_actual_child_terminal=True,
            source_Root_profile_closure=inputs['Root_profile_closure'],actual_seal_from_saved_stdout=True,
            fresh_filesystem_scan_performed=False))
    return write(output/'RESULT.json',dict(schema='native_S_saved_metadata_observation_result_v1',role=role,
        inputs=inputs_ref,profile_result=profile_ref,observation=saved,producer_source=ref(__file__),
        actual_outer_C0_not_self_asserted=True,claims_kernel_accumulator_precision=False,scientific_acceptance=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('request','request-sha256','source-pins','source-pins-sha256','expected-node','output'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--pressure-only',action='store_true')
    parser.add_argument('--pressure-input');parser.add_argument('--pressure-input-sha256')
    parser.add_argument('--pressure-wall-seconds',type=int,default=1200)
    parser.add_argument('--observation-only',action='store_true');parser.add_argument('--inputs');parser.add_argument('--inputs-sha256')
    args=parser.parse_args();request_ref=ref(args.request);pins_ref=ref(args.source_pins)
    require(request_ref['sha256']==args.request_sha256 and pins_ref['sha256']==args.source_pins_sha256,'Request/source pins SHA differs')
    request=read(request_ref);pins=read(pins_ref);folder=Path(__file__).absolute().parent;runtime=[]
    require(pins['schema']=='native_S_supplemental_readiness_source_pins_v1','Exact supplemental source inventory required')
    for row in pins['files']:
        value=dict(path=str(folder/row['relative_path']),bytes=row['bytes'],sha256=row['sha256']);bind(value);runtime.append(value)
    deps=read(next(value for value in runtime if Path(value['path']).name=='dependencies.json'))
    for value in deps['sources'].values():bind(value)
    require(request['schema']=='native_S_supplemental_readiness_request_v1' and request['principal']=='Root'
        and request['scope']=='NATIVE_S_PROFILE_READINESS_ONLY' and request['scientific_acceptance'] is False,'Explicit profile-only request required')
    require(os.environ.get('SLURM_JOB_ID','').isdigit() and os.uname().nodename==args.expected_node
        and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16 and os.environ.get('CUDA_VISIBLE_DEVICES','')=='',
        'Actual CPU-only allocation required')
    output=Path(args.output);require(output.parent==output.parent.resolve(strict=True),'Physical fresh output parent required')
    output.mkdir(mode=0o700,exist_ok=False)
    if args.pressure_only:
        value=ref(args.pressure_input);require(value['sha256']==args.pressure_input_sha256 and value==request['pressure_input'],'Pressure input raw SHA differs')
        pressure(request,deps,output,value,args.pressure_wall_seconds);return 0
    if args.observation_only:
        value=ref(args.inputs);require(value['sha256']==args.inputs_sha256 and value in request['observation_inputs'],'Observation input raw SHA differs')
        observation(value,output);return 0
    started=time.monotonic();stages=[];failure=None;code=1
    def child(label,argv,timeout):
        before=time.monotonic();started_unix=time.time();actual_argv=None;child_identity=None;timed_out=False
        path=bind(deps['sources']['Root_metadata_recorder'])
        spec=importlib.util.spec_from_file_location('readiness_bound_identity',path)
        observer=importlib.util.module_from_spec(spec);spec.loader.exec_module(observer)
        stdout=output/(label+'.stdout');stderr=output/(label+'.stderr')
        with stdout.open('xb') as out,stderr.open('xb') as err:
            proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                env={**os.environ,'PYTEST_ADDOPTS':'-o tmp_path_retention_policy=failed'})
            for _ in range(100):
                try:
                    candidate=[value.decode() for value in Path('/proc').joinpath(str(proc.pid),'cmdline').read_bytes().split(b'\0') if value]
                    if candidate==argv:
                        actual_argv=candidate;child_identity=observer.identity(proc.pid);break
                except FileNotFoundError:pass
                if proc.poll() is not None:break
                time.sleep(.01)
            try:code=proc.wait(timeout=min(timeout,max(1,1460-(time.monotonic()-started))))
            except subprocess.TimeoutExpired:
                if proc.poll() is None:proc.kill()
                code=proc.wait(timeout=10);timed_out=True
        require(actual_argv==argv and child_identity['uid']==os.getuid(),'Actual child argv/kernel identity was not observed')
        require(stdout.stat().st_size<=4<<20 and stderr.stat().st_size<=4<<20,'Bounded stage logs exceeded4MiB')
        row=dict(stage=label,argv=actual_argv,returncode=code,elapsed_seconds=time.monotonic()-before,
            started_unix=started_unix,completed_unix=time.time(),job_id=os.environ['SLURM_JOB_ID'],uid=os.getuid(),
            child_identity=child_identity,stdout=ref(stdout),stderr=ref(stderr),stage_timeout=timed_out)
        stages.append(row);write(output/(label+'_execution.json'),row)
        require(code==0 and not timed_out,'Supplemental stage failed: '+label)
    try:
        calls=request['SDK_calls'];require(len(calls)==2,'Exactly two real SDK calls required')
        read(deps['sources']['readback_pins'])
        argv=[sys.executable,'-u','-B',deps['sources']['readback_runner']['path'],'--pins-sha256',deps['sources']['readback_pins']['sha256'],
            '--expected-node',args.expected_node]
        for call in calls:bind(call);argv.extend(['--input',call['path'],'--input-sha256',call['sha256']])
        argv.extend(['--output',str(output/'SDK_readback')]);child('SDK_readback',argv,540)
        child('inventory_metadata4',[sys.executable,'-B','-m','pytest',deps['sources']['checkpoint_inventory_tests']['path'],
            '-q','-p','no:cacheprovider','-o','tmp_path_retention_policy=failed',
            '--basetemp='+str(output/'inventory_metadata_tmp'),'--junitxml='+str(output/'inventory_metadata4.xml')],60)
        counts={name:0 for name in ('tests','failures','errors','skipped')}
        for suite in ET.parse(output/'inventory_metadata4.xml').getroot().iter('testsuite'):
            for name in counts:counts[name]+=int(suite.attrib.get(name,0))
        require(counts==dict(tests=4,failures=0,errors=0,skipped=0),'Inventory four metadata/tensor cases must actually pass without skips')
        inventories=request['checkpoint_inventory_inputs'];require(len(inventories)==2,'Exactly two real CP inventories required')
        for index,value in enumerate(inventories):
            bind(value)
            child('checkpoint_inventory_'+str(index),[sys.executable,'-B',deps['sources']['checkpoint_inventory_runner']['path'],
                '--inputs',value['path'],'--output',str(output/('checkpoint_inventory_'+str(index)))],90)
            bind(value)
        for index,value in enumerate(request['observation_inputs']):
            bind(value)
            child('metadata_observation_'+str(index),[sys.executable,'-u','-B',str(Path(__file__).absolute()),
                '--request',args.request,'--request-sha256',args.request_sha256,'--source-pins',args.source_pins,
                '--source-pins-sha256',args.source_pins_sha256,'--expected-node',args.expected_node,
                '--inputs',value['path'],'--inputs-sha256',value['sha256'],'--observation-only',
                '--output',str(output/('metadata_observation_'+str(index)))],15)
        pressure_seconds=min(1200,int(1440-(time.monotonic()-started)))
        require(pressure_seconds>=60,'Shared1500s budget has no safe full-pressure window remaining')
        child('full_accounting_pressure',[sys.executable,'-u','-B',str(Path(__file__).absolute()),
            '--request',args.request,'--request-sha256',args.request_sha256,'--source-pins',args.source_pins,
            '--source-pins-sha256',args.source_pins_sha256,'--expected-node',args.expected_node,
            '--pressure-input',request['pressure_input']['path'],'--pressure-input-sha256',request['pressure_input']['sha256'],
            '--pressure-wall-seconds',str(pressure_seconds),
            '--output',str(output/'full_accounting_pressure'),'--pressure-only'],pressure_seconds+10)
        for value in runtime+list(deps['sources'].values())+list(deps['pressure_sources'].values())+inventories+request['observation_inputs']+[request_ref,pins_ref,request['pressure_input']]:bind(value)
        sdk=read(ref(output/'SDK_readback/READBACK_RESULT.json'))
        components=dict(schema='native_S_supplemental_component_index_v1',
            status='RAW_COMPONENTS_AVAILABLE_PENDING_ACTUAL_CPU_OUTER_C0',
            actual_CPU_job_id=os.environ['SLURM_JOB_ID'],actual_CPU_C0_not_self_asserted=True,
            sdk=dict(result=ref(output/'SDK_readback/READBACK_RESULT.json'),profiles=sdk['profiles'],
                raw_command=ref(output/'SDK_readback/raw_execution.json'),producer_source=deps['sources']['readback_runner']),
            future_state=[],metadata_observations=[],accounting=dict(
                raw_measurement=ref(output/'full_accounting_pressure/accounting_pressure.json'),
                inputs=request['pressure_input'],raw_command=ref(output/'full_accounting_pressure_execution.json'),producer_source=ref(__file__)),
            scientific_acceptance=False,full_storage_or_20k_acceptance=False)
        for index,value in enumerate(inventories):
            saved=read(ref(output/('checkpoint_inventory_'+str(index))/'RESULT.json'))
            components['future_state'].append(dict(inputs=value,shape_report=saved['shape_report'],
                future_bound_calculation=saved['future_bound_calculation'],
                raw_command=ref(output/('checkpoint_inventory_'+str(index)+'_execution.json')),
                producer_source=deps['sources']['checkpoint_inventory_runner']))
        for index,value in enumerate(request['observation_inputs']):
            saved=read(ref(output/('metadata_observation_'+str(index))/'RESULT.json'))
            components['metadata_observations'].append(dict(inputs=value,result=ref(output/('metadata_observation_'+str(index))/'RESULT.json'),
                role=saved['role'],profile_result=saved['profile_result'],observation=saved['observation'],
                raw_command=ref(output/('metadata_observation_'+str(index)+'_execution.json')),producer_source=ref(__file__)))
        write(output/'COMPONENT_INDEX.json',components)
        code=0
    except Exception as error:failure=dict(type=type(error).__name__,message=str(error)[:1800])
    raw_argv=[value.decode() for value in Path('/proc/self/cmdline').read_bytes().split(b'\0') if value]
    write(output/'READINESS_RESULT.json',dict(schema='native_S_supplemental_readiness_result_v1',
        status='READINESS_CHILD_COMPLETE_PENDING_ACTUAL_CPU_C0' if code==0 else 'FAILED_PRESERVED',
        returncode=code,failure=failure,stages=stages,actual_argv=raw_argv,job_id=os.environ['SLURM_JOB_ID'],
        actual_CPU_C0_not_self_asserted=True,scientific_acceptance=False,production_20k_allowed=False,
        elapsed_seconds=time.monotonic()-started))
    return code


if __name__=='__main__':raise SystemExit(main())
