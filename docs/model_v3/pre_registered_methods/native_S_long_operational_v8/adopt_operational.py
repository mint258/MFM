"""Resource-only v8 adoption while Root's original-dispatch boundary is held.

No training, Slurm submission, payload read, signal, or generated future proof.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import xml.etree.ElementTree as ET
from long_common import *
import quota_publish
from publication import verify_method

V7=N/'native_S_long_operational_v7'
GATE=N/'native_B_auto_memory_boundary_v1_source/boundary_gate.py'
CONTROLLER=N/'native_B_remaining_20261029'
TEST_NAMES=('test_long_contract.py','test_quota_retry.py','test_quota_publish.py','test_auto_resources.py')

def actual_CPU_QA(inputs,manifest):
    request=read_ref(inputs['unit_request']);summary=read_ref(inputs['summary'])
    unit=read_ref(inputs['unit_result']);supervisor=read_ref(inputs['supervisor'])
    raw=read_ref(inputs['actual_sacct']);job=summary['job_id']
    require(type(job) is str and job.isdigit() and raw['returncode']==0 and raw['stderr']==''
        and raw['argv']==['sacct','-X','-n','-P','-j',job,
            '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],
        'Actual exact-parent CPU accounting observation required')
    lines=[line.split('|') for line in raw['stdout'].splitlines() if line.strip()]
    require(len(lines)==1 and len(lines[0])==7 and lines[0][0]==job
        and lines[0][1:4]==['zixiao','COMPLETED','0:0'] and lines[0][4].isdigit()
        and int(lines[0][4])>0 and lines[0][5]=='16'
        and lines[0][6] in ['compute-0-'+str(i) for i in (2,*range(8,20))],
        'Owned actual16CPU C0 on a CPU node required')
    require(summary['status']=='PASS' and summary['node']==lines[0][6]
        and summary['cuda_visible_devices']=='' and summary['requested_cpus']=='16'
        and summary['request_sha256']==inputs['unit_request']['sha256']
        and summary['runner_sha256']==binding(OLD/'run_frozen_units_v1.py')['sha256'],
        'Actual original frozen-units CPU summary differs')
    require(request['schema']=='model_v3_frozen_units_request_v1'
        and unit in summary['units'] and unit['name']==inputs['unit_name']
        and unit['returncode']==0 and unit['sources_unchanged'] is True
        and unit['counts']==dict(tests=34,failures=0,errors=0,skipped=0),
        'Complete original30 and four actual resource metadata controls required')
    tasks=[row for row in request['tasks'] if row['name']==unit['name']]
    require(len(tasks)==1,'Exact actual CPU task required');task=tasks[0]
    require(task['tests']==[str(HERE/name) for name in TEST_NAMES]
        and task.get('environment',{}).get('PYTEST_ADDOPTS')=='-o tmp_path_retention_policy=failed',
        'Four complete metadata modules/failed-only fixture policy required')
    before=unit['source_hashes_before']
    require(before==unit['source_hashes_after']==task['sources'],'Actual QA source-before/after differs')
    protected=[binding(HERE/row['path']) for row in read_ref(manifest)['files']]+[manifest]
    protected+=read(HERE/'dependency_pins.json')['references']
    for ref in protected:
        require(before.get(ref['path'])==ref['sha256'] and binding(ref['path'])==ref,
            'Actual same-source tested/current v8 or protected source absent/changed')
    xml_ref=inputs['JUnit'];require(binding(xml_ref['path'])==xml_ref,'Actual JUnit differs')
    argv=unit['argv'];expected=[summary['python_executable'],'-B','-m','pytest',
        *[str(HERE/name) for name in TEST_NAMES],'-q','-p','no:cacheprovider','--junitxml='+xml_ref['path']]
    require(argv[:-1]==expected and len(argv)==len(expected)+1 and argv[-1].startswith('--basetemp='),
        'Actual complete unfiltered pytest invocation differs')
    counts={key:0 for key in ('tests','failures','errors','skipped')}
    for suite in ET.fromstring(Path(xml_ref['path']).read_bytes()).iter('testsuite'):
        for key in counts:counts[key]+=int(suite.attrib.get(key,0))
    require(counts==unit['counts'],'Actual JUnit/JSON counts differ')
    require(supervisor['status']=='COMPLETED' and supervisor['exit_code']==0
        and str(supervisor['job_id'])==job and supervisor['first_failure'] is None
        and supervisor['remaining']==[] and supervisor['gpu_initialization_permitted'] is False
        and supervisor['private_storage']['first_sampling_failure'] is None,
        'Actual CPU supervisor/process/private cleanup incomplete')
    return dict(status='ACTUAL_C0_34_METADATA_TESTS_SOURCE_CLOSED',job_id=job,counts=counts,
        unit_request=inputs['unit_request'],summary=inputs['summary'],unit_result=inputs['unit_result'],
        JUnit=xml_ref,supervisor=inputs['supervisor'],actual_sacct=inputs['actual_sacct'],
        same_current_source_map_verified=True,science_acceptance=False)



def original_adoption(phase):
    frozen_verify(V7,'83f05fff155204fc4443803aba67107cc8d4d63bc6c4452e5ec098e294e31bf1')
    value_ref=binding(phase/'control/OPERATIONAL_ADOPTION_v7.json');value=read_ref(value_ref)
    original=binding(phase/'control/VALIDATED.json');validated=read_ref(original)
    require(value['schema']=='native_S_long_operational_adoption_v7' and value['authority']=='ROOT_ACTUAL'
        and value['original_validation']==original and value['original_package']==validated['package_manifest']
        and value['package_manifest']==binding(V7/'source_pins.json')
        and value['principal']==binding(phase/'control/principal.json')
        and value['counters_reset'] is False
        and value['numerical_science_config_data_seed_precision_unchanged'] is True,
        'Actual original v7 adoption/scientific chain required')
    for name in ('configuration','profile','initial_roots','runtime_contract','registry'):
        require(value[name]==validated[name],'Original scientific binding changed')
    for name in ('original_failed_closure','prior_operational_adoption','failed_v5_operational_adoption',
                 'failed_v5_package_manifest','failed_v6_operational_adoption','failed_v6_package_manifest'):
        read_ref(value[name])
    for name in ('failed_v5_coordinator_stdout','failed_v6_coordinator_stdout'):
        require(binding(value[name]['path'])==value[name],'Retained historical plain-text log changed')
    require(value['failed_v5_no_fresh_lease_intent_submission_or_slot'] is True
        and value['failed_v6_no_fresh_lease_intent_submission_or_slot'] is True,'Historical failed pre-SB facts differ')
    qa=value['actual_CPU_QA']
    require(qa['status']=='ACTUAL_C0_30_METADATA_TESTS_SOURCE_CLOSED'
        and qa['counts']==dict(tests=30,failures=0,errors=0,skipped=0)
        and read_ref(qa['summary'])['status']=='PASS' and read_ref(qa['unit_result'])['counts']==qa['counts'],
        'Retained actual v7 QA is historical, not v8 QA')
    require(binding(phase/'control/quota_descriptor_v7.json')==value['quota_feed_descriptor'],
        'Retained v7 quota producer descriptor changed')
    return value_ref,value,validated


def boundary_held(item,phase):
    require(binding(item['path'])==item,'Actual held-boundary rawref changed')
    held=read_ref(item);out=Path(item['path']).parent
    require(out.parent==N and out.name.startswith('native_B_auto_memory_boundary_')
        and held['schema']=='native_B_Root_dispatch_boundary_held_v1'
        and held['status']=='ORIGINAL_C0_SEGMENT_CLOSED_CONTROLLER_GONE_NO_NEW_ATTEMPT_MUTEX_HELD'
        and held['authority']=='ROOT_ACTUAL' and held['no_signal_or_submission_performed'] is True
        and not (out/'RELEASE.json').exists() and not (out/'RELEASE_ACTUAL.json').exists(),
        'Root boundary must still be held and unreleased')
    identity=read_ref(held['identity']);pid=identity['pid'];proc=Path('/proc')/str(pid)
    require(type(pid) is int and identity['uid']==os.getuid()==1278 and proc.stat().st_uid==1278
        and identity['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        and identity['source']==binding(GATE), 'Exact live reviewed gate identity/source required')
    tail=(proc/'stat').read_text().rsplit(')',1)[1].split()
    require(int(tail[19])==identity['start_ticks'] and tail[0]!='Z'
        and hashlib.sha256((proc/'cmdline').read_bytes()).hexdigest()==identity['argv_sha256']
        and os.getpgid(pid)==identity['pgid'] and os.getsid(pid)==identity['sid'], 'Gate process identity changed')
    require(not Path('/proc/3244560').exists(),'Original controller must be actually gone')
    for path in (phase/'control/.dispatch.lock',CONTROLLER/'controller.lock'):
        expected=path.stat();found=[]
        for fd in (proc/'fd').iterdir():
            try:
                actual=fd.stat()
                text=(proc/'fdinfo'/fd.name).read_text()
            except FileNotFoundError:
                continue
            if (actual.st_dev,actual.st_ino)==(expected.st_dev,expected.st_ino):
                found.append(text)
        require(any(re.search(r'^lock:\s+.*\bFLOCK\s+ADVISORY\s+WRITE\s+'+str(pid)+r'\s',text,re.M)
                    for text in found),'Actual gate must hold both original mutex inodes')
    state=read(out/'status.json')
    require(state['status']=='BOUNDARY_HELD_PENDING_ROOT_EXPLICIT_RELEASE'
        and state['identity']==held['identity'] and state['boundary_receipt']==item,'Gate status is not held')
    from long_operations import closed_attempts,next_member
    attempts=closed_attempts(phase)
    require(attempts and attempts[-1][2]==held['boundary']['last']['closure']
        and attempts[-1][1]['status']=='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING', 'Latest closed segment differs')
    snapshots=dict(attempts={p.name:binding(p) for p in sorted((phase/'control/attempts').glob('slot_*.json'))},
        leases={p.name:binding(p) for p in sorted((phase/'control/leases').glob('*.json'))})
    require(snapshots==held['phase_snapshot'],'Attempt/lease population changed after boundary acquisition')
    return held,next_member(phase)


def verified_adoption(phase,manifest):
    prior_ref,prior,validated=original_adoption(phase)
    item=binding(phase/'control/OPERATIONAL_ADOPTION_v8.json');value=read_ref(item)
    require(value['schema']=='native_S_long_operational_adoption_v8' and value['authority']=='ROOT_ACTUAL'
        and value['package_manifest']==manifest and value['previous_operational_adoption_v7']==prior_ref
        and value['prior_v7_CPU_QA']==prior['actual_CPU_QA'] and value['original_validation']==prior['original_validation']
        and value['principal']==prior['principal'] and value['counters_reset'] is False
        and value['numerical_science_config_data_seed_precision_unchanged'] is True,
        'Independent resource-only v8 adoption required')
    for name in ('configuration','profile','initial_roots','runtime_contract','registry','orphan_prelaunch'):
        require(value[name]==prior[name],'Resource adoption changed original science/lease authority')
    qa=value['actual_CPU_QA']
    require(qa['status']=='ACTUAL_C0_34_METADATA_TESTS_SOURCE_CLOSED'
        and qa['counts']==dict(tests=34,failures=0,errors=0,skipped=0)
        and read_ref(qa['summary'])['status']=='PASS' and read_ref(qa['unit_result'])['counts']==qa['counts'],
        'Actual v8 metadata QA required; v7 result is not v8 evidence')
    require(binding(phase/'control/quota_descriptor_v8.json')==value['quota_feed_descriptor'], 'Actual v8 descriptor differs')
    verify_method(value['method_publication'])
    require(value['user_auto_memory_approval']==binding(N/'MODEL_GPU_AUTO_MEMORY_USER_APPROVAL_20261029_v1.json')
        and read_ref(value['user_auto_memory_approval'])['status']=='USER_EXPLICITLY_APPROVED', 'Actual GPU-auto approval required')
    held=read_ref(value['switch_boundary']);out=Path(value['switch_boundary']['path']).parent
    release_ref=binding(out/'RELEASE_ACTUAL.json');release=read_ref(release_ref)
    request=read_ref(release['release_request'])
    require(release['status']=='ROOT_EXPLICIT_RELEASE_NO_SUBMISSION'
        and release['boundary_receipt']==value['switch_boundary'] and release['no_submission_performed'] is True
        and request['new_operations_source_pins']==manifest and request['new_operations_adoption']==item
        and request['method_publication']==value['method_publication']
        and not Path('/proc/'+str(read_ref(held['identity'])['pid'])).exists()
        and not Path('/proc/3244560').exists(), 'Root must explicitly release the actual boundary before separate submit')
    return item,value


def main():
    root_identity();parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',type=Path,required=True);parser.add_argument('--pins-sha256',required=True)
    parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--inputs-sha256',required=True)
    args=parser.parse_args();manifest,_=verify(args.pins_sha256)
    input_ref=binding(args.inputs);require(input_ref['sha256']==args.inputs_sha256,'Actual Root input rawSHA required')
    inputs=read_ref(input_ref)
    require(inputs['schema']=='native_S_long_v8_resource_adoption_inputs_v1','Explicit post-QA resource-only inputs required')
    phase=args.phase.absolute();require(phase==N/'native_S_B20k_v3','Only original B lineage may adopt resource-only v8')
    require(not (phase/'control/OPERATIONAL_ADOPTION_v8.json').exists(),'Never overwrite an adoption')
    prior_ref,prior,validated=original_adoption(phase)
    qa=actual_CPU_QA(inputs,manifest)
    verify_method(inputs['method_publication'])
    approval=binding(N/'MODEL_GPU_AUTO_MEMORY_USER_APPROVAL_20261029_v1.json')
    require(read_ref(approval)['status']=='USER_EXPLICITLY_APPROVED','Actual user GPU-auto approval required')
    held,next_step=boundary_held(inputs['switch_boundary'],phase)
    descriptor=quota_publish.ensure_descriptor(phase)
    result=write(phase/'control/OPERATIONAL_ADOPTION_v8.json',dict(prior,
        schema='native_S_long_operational_adoption_v8',package_manifest=manifest,
        previous_operational_adoption_v7=prior_ref,prior_v7_CPU_QA=prior['actual_CPU_QA'],actual_CPU_QA=qa,
        quota_feed_descriptor=descriptor,Root_inputs=input_ref,switch_boundary=inputs['switch_boundary'],
        method_publication=inputs['method_publication'],user_auto_memory_approval=approval,
        next_step_at_adoption=next_step,Slurm_memory_mode='automatic_default',software_budget_bytes=32<<30,
        software_RSS_guard_bytes=RSS,scientific_acceptance=False))
    boundary_held(inputs['switch_boundary'],phase)
    print(json.dumps(dict(status='OPERATIONAL_V8_RESOURCE_ADOPTED_NO_SUBMISSION',adoption=result,next=next_step)))


if __name__=='__main__':main()
