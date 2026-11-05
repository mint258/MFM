"""Prepare only closed metadata; audit <=3 closed native long SDKs on one CPU job."""
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
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
sys.dont_write_bytecode=True
HERE=Path(__file__).absolute().parent
MAX_META=32<<20


def require(ok,message):
    if not ok:raise ValueError(message)


def physical(path):
    path=Path(path);require(path.is_absolute() and path==path.resolve(strict=True) and '..' not in path.parts,'Physical absolute owned path required')
    return path


def descriptor(path,cap):
    path=physical(path);st=path.stat()
    require(path.is_file() and st.st_uid==os.getuid() and st.st_nlink==1 and 0<st.st_size<=cap,'Bounded owned ordinary file required')
    return dict(path=str(path),bytes=st.st_size)


def ref(path,cap=MAX_META):
    value=descriptor(path,cap);path=Path(value['path']);before=path.stat();digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):digest.update(block)
    after=path.stat()
    require((before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),'File changed during hash')
    return {**value,'sha256':digest.hexdigest()}


def bind(value,cap=MAX_META):
    require(set(value)=={'path','bytes','sha256'} and re.fullmatch('[0-9a-f]{64}',value['sha256']) and ref(value['path'],cap)==value,'Raw-byte reference differs')
    return Path(value['path'])


def read(value):
    def pairs(items):
        result={}
        for key,item in items:require(key not in result,'Duplicate metadata JSON key');result[key]=item
        return result
    return json.loads(bind(value).read_bytes(),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite metadata literal')))


def write(path,value):
    raw=(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    require(len(raw)<=4<<20,'Compact certificate only')
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return ref(path)


def load(value,name):
    path=bind(value);spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def terminal(value,job):
    body=read(value);raw=read(body['raw_sacct']);argv=raw['argv']
    require(body['schema']=='native_S_actual_terminal_projection_v2' and str(body['job_id'])==job
        and body['status']=='COMPLETED' and body['exit_code']==0 and raw['returncode']==0
        and Path(argv[0]).name=='sacct','Actual closed segment sacct C0 required')
    options=[item.split('=',1)[1] for item in argv if item.startswith('--format=')]
    require(len(options)==1 and '-j' in argv and job in argv[argv.index('-j')+1].split(','),'Exact parent sacct query required')
    names=options[0].split(',');rows=[dict(zip(names,line.split('|'))) for line in raw['stdout'].splitlines()]
    rows=[row for row in rows if row.get('JobIDRaw',row.get('JobID'))==job]
    require(len(rows)==1 and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0','Actual segment raw terminal is not C0')


def closed(child):
    child=physical(child);management=child.parent/'management';closure_ref=ref(management/'ROOT_LONG_SEGMENT_CLOSURE.json');closure=read(closure_ref)
    require(closure['schema']=='native_S_long_segment_Root_closure_v1'
        and closure['status']=='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING' and closure['failure'] is None,'Only explicit actually closed long segments may be prepared')
    submission=read(closure['submission']);job=str(submission['actual_sbatch_job_id']);terminal(closure['actual_terminal'],job)
    require(submission['child_root']==str(child) and Path(closure['member_result']['path'])==child/'member_result.json','Segment source/root identity differs')
    sup=read(closure['supervisor'])
    require(str(sup['job_id'])==job and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
        and sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[],
        'Actual segment process/private closure required')
    seal=read(closure['storage_seal']);require(seal['returncode']==0,'Root closed storage-seal invocation failed')
    refs=dict(closure=closure_ref,submission=closure['submission'],terminal=closure['actual_terminal'],
        supervisor=closure['supervisor'],seal_execution=closure['storage_seal'],member=closure['member_result'],
        configuration=ref(child/'configuration.json'),status=ref(child/'run_status.json'),
        expected_configuration=ref(child/'SDK_expected_configuration.json'),expected_summary=ref(child/'SDK_expected_summary.json'))
    return refs


def prepare_inputs(args):
    phase=physical(args.phase);slots=args.slot or []
    require(1<=len(slots)<=3 and len(set(slots))==len(slots) and all(1<=slot<=108 for slot in slots),'One to three explicit finite closed slots only')
    values=[]
    for slot in slots:
        child=phase/'slots'/f'slot_{slot:03d}'/'child';refs=closed(child);cfg=read(refs['configuration']);expected=read(refs['expected_configuration'])
        run_id=cfg['tracker']['id'];sdk=list((child/'wandb').glob('offline-run-*/run-'+run_id+'.wandb'))
        require(len(sdk)==1,'One exact closed per-segment native SDK required')
        parent=None
        if expected['resume_output_root'] is not None:
            parent_child=physical(expected['resume_output_root']);require(parent_child.is_relative_to(phase/'slots'),'Resume parent must be in this retained phase')
            parent=dict(child_path=str(parent_child),refs=closed(parent_child),mirror=descriptor(parent_child/'history.jsonl',128<<20))
        values.append(dict(slot=slot,child_path=str(child),refs=refs,sdk=descriptor(sdk[0],128<<20),
            mirror=descriptor(child/'history.jsonl',128<<20),parent=parent))
    out=Path(args.output);require(out.parent==out.parent.resolve(strict=True) and not out.exists(),'Fresh physical prepared-input output required')
    out.mkdir(mode=0o700)
    value=dict(schema='native_S_closed_long_segment_log_inputs_v1',scope='LONG_SEGMENT_LOG_ONLY',segments=values,
        SDK_and_history_payloads_not_read_by_prepare=True,CP_payload_not_read=True,scientific_acceptance=False)
    result=write(out/'INPUTS.json',value);print(json.dumps(result));return 0


def mirror(value,reader):
    require(descriptor(value['path'],128<<20)==value,'Closed mirror descriptor changed before CPU binding')
    before=ref(value['path'],128<<20);rows=[]
    with Path(value['path']).open('rb') as stream:
        for line in stream:
            require(len(rows)<1104 and len(line)<=reader.MAX_LINE_BYTES and line.endswith(b'\n'),'Bounded complete closed long mirror required')
            rows.append(reader.strict_json(line))
    bind(before,128<<20);return rows,before


def run_one(item,out,deps,modules):
    started=time.monotonic();deadline=started+180;reader,tap,framing,logic=modules
    # Revalidate raw C0/process/source closure; a pre-existing profile certificate is never used.
    current=closed(Path(item['child_path']));require(current==item['refs'],'Closed segment metadata drifted')
    metadata={key:read(value) for key,value in current.items() if key in ('closure','submission','member','configuration','status','expected_configuration','expected_summary')}
    cfg=metadata['configuration']
    retry_binding=logic.check_operational_sources(cfg,metadata['expected_configuration'],deps['sources'])
    require(metadata['submission']['package_manifest']==deps['sources']['operational_package'],
        'Actual v4 segment source manifest differs')
    adoption=read(metadata['submission']['operational_adoption'])
    require(adoption['schema']=='native_S_long_operational_adoption_v4' and adoption['authority']=='ROOT_ACTUAL'
        and adoption['package_manifest']==deps['sources']['operational_package']
        and adoption['configuration']==metadata['submission']['configuration']
        and adoption['principal']==metadata['submission']['principal']
        and adoption['numerical_science_config_data_seed_precision_unchanged'] is True
        and adoption['counters_reset'] is False,'Actual operational-only source adoption differs')
    rows,mirror_ref=mirror(item['mirror'],reader);parent_rows=None;all_refs=list(current.values())+[mirror_ref,
        read(current['terminal'])['raw_sacct'],metadata['submission']['operational_adoption']]
    if item['parent'] is not None:
        parent=item['parent'];require(closed(Path(parent['child_path']))==parent['refs'],'Closed parent metadata drifted')
        parent_rows,parent_ref=mirror(parent['mirror'],reader)
        metadata['parent']={key:read(parent['refs'][key]) for key in ('member','configuration','closure')}
        metadata['parent']['child_path']=parent['child_path'];all_refs+=list(parent['refs'].values())+[parent_ref,read(parent['refs']['terminal'])['raw_sacct']]
    context=logic.prepare(metadata,rows,parent_rows=parent_rows)
    require(descriptor(item['sdk']['path'],128<<20)==item['sdk'],'Closed SDK path/byte size changed')
    sdk_ref=ref(item['sdk']['path'],128<<20);all_refs.append(sdk_ref)
    from wandb.sdk.internal.datastore import DataStore
    from wandb.proto import wandb_internal_pb2 as pb
    require(importlib.metadata.version('wandb')==deps['decoder']['WandB_version'],'Installed decoder version differs')
    installed=dict(DataStore=framing.installed_source(inspect.getfile(DataStore)),Record_module=framing.installed_source(pb.__file__))
    require(installed['DataStore']['sha256']==deps['decoder']['DataStore_expected_sha256']
        and installed['Record_module']['sha256']==deps['decoder']['Record_module_expected_sha256'],'Actual decoder source differs')
    scanner=framing.read_only_scanner(DataStore,importlib.import_module(DataStore.__module__))()
    scanner._deadline=deadline;scanner._record_bytes_limit=4<<20
    try:
        scanner.open_for_scan(sdk_ref['path']);result=logic.compare(reader,tap,scanner,pb.Record,context,deadline=deadline)
    finally:scanner.close()
    for value in all_refs:bind(value,128<<20)
    require(time.monotonic()<=deadline,'Inclusive180s long log audit budget exceeded')
    for name,value in installed.items():require(framing.installed_source(value['path'])==value,'Installed decoder changed')
    result.update(sdk=sdk_ref,mirror=mirror_ref,closed_metadata_refs=current,history_reader_source=deps['sources']['reader'],
        tap_source=deps['sources']['tap'],installed_decoder_sources=installed,elapsed_seconds=time.monotonic()-started,
        operational_quota_revalidation=retry_binding,operational_package=deps['sources']['operational_package'],
        operational_adoption=metadata['submission']['operational_adoption'],
        raw_before_after_binding_closed=True,parent_or_profile_C0_not_used_as_native_log_proof=True)
    out.mkdir(mode=0o700);return write(out/'VERIFICATION.json',result)


def run(args):
    pins_ref=ref(HERE/'source_pins.json');require(pins_ref['sha256']==args.pins_sha256,'Own source pins raw SHA differs');pins=read(pins_ref);runtime=[]
    require(pins['schema']=='native_S_long_segment_log_source_pins_v2','Exact long-log-only source pins required')
    for row in pins['files']:
        value=dict(path=str(HERE/row['file']),bytes=row['bytes'],sha256=row['sha256']);bind(value);runtime.append(value)
    deps=read(next(value for value in runtime if Path(value['path']).name=='dependencies.json'))
    for value in deps['sources'].values():bind(value)
    require(os.environ.get('SLURM_JOB_ID','').isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16
        and os.environ.get('CUDA_VISIBLE_DEVICES')=='' and socket.gethostname()==args.expected_node
        and re.fullmatch('compute-0-(?:2|[8-9]|1[0-9])',args.expected_node),'Real CPU-only>=16CPU allocation required')
    job=os.environ['SLURM_JOB_ID'];group=Path('/proc/self/cgroup').read_text()
    require(re.search(r'(?:^|/)job[_/-]'+re.escape(job)+r'(?:/|$)',group,re.M),'Own kernel job cgroup required')
    inputs=ref(args.inputs);require(inputs['sha256']==args.inputs_sha256,'Closed batch input SHA differs');batch=read(inputs)
    require(batch['schema']=='native_S_closed_long_segment_log_inputs_v1' and batch['scope']=='LONG_SEGMENT_LOG_ONLY'
        and 1<=len(batch['segments'])<=3 and len({item['child_path'] for item in batch['segments']})==len(batch['segments']),
        'One to three explicit distinct closed segments required')
    out=Path(args.output);require(out.parent==out.parent.resolve(strict=True) and not out.exists(),'Fresh audit output only');out.mkdir(mode=0o700)
    results=[];failure=None;code=1
    try:
        xml=out/'metadata.xml'
        with (out/'metadata.stdout').open('xb') as stream:
            qa=subprocess.run([sys.executable,'-B','-m','pytest',str(HERE/'test_long_segment_log.py'),'-q','-p','no:cacheprovider',
                '-o','tmp_path_retention_policy=failed','--junitxml='+str(xml)],stdout=stream,stderr=subprocess.STDOUT,timeout=90,check=False)
        counts={name:0 for name in ('tests','failures','errors','skipped')}
        for suite in ET.parse(xml).getroot().iter('testsuite'):
            for name in counts:counts[name]+=int(suite.attrib.get(name,0))
        require(qa.returncode==0 and counts==dict(tests=pins['metadata_tests'],failures=0,errors=0,skipped=0),'Actual zero-skip metadata regressions required')
        modules=(load(deps['sources']['reader'],'long_log_reader'),load(deps['sources']['tap'],'long_log_tap'),
            load(deps['sources']['framing'],'long_log_framing'),load(next(value for value in runtime if Path(value['path']).name=='long_segment_log.py'),'long_log_logic'))
        for index,item in enumerate(batch['segments']):results.append(run_one(item,out/str(index),deps,modules))
        for value in runtime+list(deps['sources'].values())+[inputs,pins_ref]:bind(value)
        code=0
    except Exception as error:failure=dict(type=type(error).__name__,message=str(error)[:1800])
    write(out/'BATCH_RESULT.json',dict(schema='native_S_long_segment_log_audit_batch_v1',scope='LONG_SEGMENT_LOG_ONLY',
        status='CLOSED_SEGMENT_LOGS_MATCHED_PENDING_CPU_OUTER_C0' if code==0 else 'FAILED_PRESERVED',
        inputs=inputs,verifications=results,failure=failure,actual_job_id=job,uid=os.getuid(),
        actual_argv=[part.decode() for part in Path('/proc/self/cmdline').read_bytes().split(b'\0') if part],
        returncode=code,own_C0_not_asserted=True,source_pins=pins_ref,scientific_acceptance=False,B_acceptance=False))
    return code


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='mode',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--phase',type=Path,required=True);prep.add_argument('--slot',type=int,action='append',required=True);prep.add_argument('--output',type=Path,required=True)
    audit=sub.add_parser('run')
    for name in ('inputs','inputs-sha256','pins-sha256','expected-node','output'):audit.add_argument('--'+name,required=True)
    args=parser.parse_args();return prepare_inputs(args) if args.mode=='prepare' else run(args)


if __name__=='__main__':raise SystemExit(main())
