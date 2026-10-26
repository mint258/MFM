"""Source-bound projection of Root's already completed full regression.

Reads bounded code/test evidence, never data/weights or an invented PASS. This
unblocks only the runtime gate; the launch package still admits PROFILE20 only.
"""
from common import *

def build(root,metadata,checker):
    source=OLD/'native_s_precision_identity_v4_retry1_complete.json'
    pinned=[row for row in read(HERE/'dependency_pins.json')['references'] if row['path']==str(source)]
    require(len(pinned)==1 and binding(source)==pinned[0],'Exact original full certificate pin required')
    certificate=read(source)
    require(certificate['schema']=='model_v3_complete_regression_validation_v4' and certificate['status']=='PASS'
        and certificate['code_commit']==CODE and certificate['partitions']==8
        and certificate['counts']==dict(tests=2592,failures=0,errors=0,skipped=3)
        and certificate['full_runtime_inventory_available'] is True,'Actual complete combined regression required')
    jobs=certificate['job_ids'];require(len(jobs)==len(set(jobs))==8,'Eight distinct actual parents required')
    require(0<len(certificate['evidence_refs'])<=256,'Bounded complete raw source graph required')
    evidence=[];evidence_bytes=0
    for item in certificate['evidence_refs']:
        path=Path(item['path']);maximum=2<<20
        if path.suffix=='.xml':
            require(path.parent.parent==OLD and path.parent.name in {'integration_tests_'+str(job) for job in jobs}
                and re.fullmatch(r'shard_0[0-3]\.xml',path.name),'Only original listed full-suite shard XML allowed')
            maximum=16<<20
        # common.binding already streams1MiB blocks and checks owner/nlink and
        # inode/device/size/mtime stability. No XML payload is loaded/parsing.
        actual_ref=binding(path,maximum=maximum)
        require(actual_ref['sha256']==item['sha256'],'Full certificate raw evidence changed')
        evidence_bytes+=actual_ref['bytes']
        require(evidence_bytes<=32<<20,'Complete original evidence graph exceeds32MiB bound')
        evidence.append(actual_ref)
    evidence_paths={r['path'] for r in evidence};parts=[];counts=dict(tests=0,failures=0,errors=0,skipped=0);seen_files=[]
    for index,job in enumerate(jobs):
        folder=OLD/f'integration_tests_{job}';before_ref=binding(folder/'sources_before.json');after_ref=binding(folder/'sources_after.json')
        require(before_ref['path'] in evidence_paths and after_ref['path'] in evidence_paths
            and before_ref['sha256']==after_ref['sha256'],'Actual full regression source inventory changed')
        before=read_ref(before_ref);require(before['git']['head']==CODE and before['git']['porcelain']=='',
            'Full suite did not run clean exact combined code')
        inventory=before['runtime']['project_source_sha256']
        require(all(inventory.get(row['relative_path'])==row['sha256'] for row in metadata['files']),
            'Actual full source inventory does not cover every current immutable runtime contract leaf')
        summary_ref=binding(folder/'summary.json');summary=read_ref(summary_ref)
        require(summary_ref['path'] in evidence_paths and summary['status']=='PASS' and summary['failure'] is None
            and summary['job_id']==str(job) and summary['code_commit']==CODE
            and summary['partition_index']==index and summary['partitions']==8
            and summary['partition_plan_sha256']==certificate['assignment_sha256']
            and summary['all_test_file_sha256']==certificate['test_source_sha256'],
            'Actual full-suite partition/assignment/source closure differs')
        supervisor_ref=binding(OLD/f'integration_supervisor_{job}.json');supervisor=read_ref(supervisor_ref)
        require(supervisor_ref['path'] in evidence_paths and supervisor['status']=='COMPLETED'
            and supervisor['exit_code']==0 and supervisor['first_failure'] is None and supervisor['remaining']==[]
            and supervisor['cleanup_diagnostics']==[] and supervisor['private_storage']['first_sampling_failure'] is None,
            'Actual full-suite CPU supervisor/process/private closure differs')
        for shard in range(4):
            ref=binding(folder/f'shard_{shard:02}.json');require(ref['path'] in evidence_paths,'Missing raw shard ref')
            value=read_ref(ref);require(value['returncode']==0 and value['counts']['failures']==value['counts']['errors']==0,
                'Raw full-suite shard failed')
            for key in counts:counts[key]+=value['counts'][key]
            seen_files.extend(value['files'])
        raw=actual(['sacct','-X','-n','-P','-j',str(job),'--format=JobIDRaw,State,ExitCode']);require_C0(raw,job)
        raw_ref=write(Path(root)/f'full_raw_sacct_{job}.json',raw)
        terminal=write(Path(root)/f'full_terminal_{job}.json',dict(schema='native_S_actual_terminal_projection_v2',
            job_id=str(job),status='COMPLETED',exit_code=0,raw_sacct=raw_ref))
        parts.append(dict(actual_terminal=terminal,raw_result=summary_ref,
            source_before_sha256=before_ref['sha256'],source_after_sha256=after_ref['sha256'],
            source_before=before_ref,source_after=after_ref,actual_CPU_supervisor=supervisor_ref))
    require(counts==certificate['counts'] and len(seen_files)==len(set(seen_files))==certificate['test_file_count']
        and set(seen_files)==set(certificate['test_source_sha256']),
        'Full-suite exact collection/assignment/counts are not the fixed actual complete certificate')
    value=dict(schema='native_S_full_runtime_verification_v2',status='FULL_RUNTIME_VERIFIED',combined_commit=CODE,
        combined_tree=TREE,full_suite_parts=parts,checker=checker,failed=0,passed=2589,collected=2592,skipped=3,
        original_full_certificate=binding(source),all_original_evidence_refs=evidence,
        original_evidence_total_bytes=evidence_bytes,original_evidence_total_bound_bytes=32<<20,
        original_XML_stream_hash_maximum_bytes=16<<20,other_metadata_maximum_bytes=2<<20,
        real_reader1_is_separate='4521104_C0_not_replaced_by_3_optional_skips',
        authority_scope='runtime_regression_only; not_profile_or_B20k_acceptance')
    return write(Path(root)/'full_runtime_verification.json',value)
