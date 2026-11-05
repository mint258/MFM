"""Root stdlib metadata closure for actual AV4521641; no model/payload reruns.

Only recorded source, publication, comparison truth, resource and accounting
metadata are verified. AV scientific error metrics/CSV are never aggregated.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import stat
import subprocess

B = Path('/share/home/zixiao/descriptor_analysis')
O = B/'runs/model_v3_20261025'
N = B/'runs/model_v3_20261026'
D = O/'attention_AV_centering_GPU_v1_4521641'
S = N/'attention_av_centering_v1_source'
JOB = '4521641'
PIN = '1a41f552eb7e9078022578e4f5b1727480d94d2ce640b8e846533c1c689d5556'
UUID = 'GPU-c35f2434-9137-9723-1af5-dc69b6295243'
PUB = N/'reporting_publication_actual_v11.json'
PUB_SHA = 'c2413c4b086d7e71ce32ca7e76a4a6149001250f6c60f4f6c40b030b05b5fe58'
PUBLIC_COMMIT = '99788277501ceff4a8adf37f7d9ee01498b9dbf1'
CORRECTION = N/'reporting_publication_v11_payload_SHA_correction_actual_v1.json'
CORRECTION_SHA = 'f2e3a0df21fd8dd6c8c61daefb7c262f1a9f5460ae81bc592c867e1b53314b2a'
ALLOWED = {'.py', '.json', '.jsonl', '.md', '.sbatch'}
COUNTS = {'scientific_encoder_forwards':192, 'captured_AV':1152,
          'original_AV_replays':1152, 'centered_controls':1152,
          'FP64_Rraw_calls':1152, 'FP64_Rnorm_calls':1152, 'FP64_Cexact_calls':1152}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def rawref(path, maximum=2<<20):
    path = Path(path).absolute()
    require(path.is_relative_to(B) and path.suffix in ALLOWED,
            'Only explicit bounded project source/JSON metadata may be opened')
    before = path.lstat()
    require(path == path.resolve(strict=True) and stat.S_ISREG(before.st_mode)
            and before.st_uid == os.getuid() and before.st_nlink == 1 and before.st_size <= maximum,
            'Owned physical ordinary bounded metadata required')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1<<20), b''):
            digest.update(block)
    after = path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) ==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns), 'Metadata changed while hashing')
    return {'path':str(path), 'bytes':before.st_size, 'sha256':digest.hexdigest()}


def read(path, maximum=2<<20):
    initial = rawref(path, maximum)
    def unique(items):
        result = {}
        for key,value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    result = json.loads(Path(path).read_bytes(), object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON literal')))
    require(rawref(path,maximum) == initial, 'Metadata changed while decoding')
    return result


def bound(value):
    require(set(value) == {'path','bytes','sha256'} and rawref(value['path']) == value,
            'Exact raw reference differs')
    return read(value['path'])


def audit_identity(value):
    require(value['independently_evaluated'] is True
        and value['bound_is_not_original_physics_tolerance'] is True
        and type(value['maxabs']) in (float,int) and type(value['floating_audit_bound']) in (float,int)
        and math.isfinite(value['maxabs']) and math.isfinite(value['floating_audit_bound'])
        and 0 <= value['maxabs'] <= value['floating_audit_bound'],
        'Recorded independent identity audit did not pass its declared floating bound')


def tiny_check(tiny):
    require(tiny['scope'] == 'INLINE_TINY_REAL_CUDA_CAPTURE_REPLAY_IDENTITY_NOT_SCIENTIFIC_CASES'
        and tiny['scientific_seed_or_model_changed'] is False, 'Tiny scope differs')
    expected = {'tiny_attention_forward_returns':3, 'tiny_supported_attention_forward_returns':2,
        'tiny_all_masked_negative_forward_returns':1, 'tiny_dropout_refused_before_forward':1,
        'tiny_original_AV_replays':2, 'tiny_centered_controls':2,
        'tiny_FP64_Rraw_calls':2, 'tiny_FP64_Rnorm_calls':2, 'tiny_FP64_Cexact_calls':2}
    require(all(tiny[key] == count for key,count in expected.items()), 'Separate tiny counts differ')
    require(tiny['negative_controls'] == {'all_masked_graph_refused_after_original_return':True,
        'effective_dropout_refused_before_original_attention':True}, 'Negative controls differ')
    require([x['class'] for x in tiny['records']] == ['DenseGeoSelfAttention','SharedPairAttention'],
            'Both actual coupled tiny classes required')
    for row in tiny['records']:
        require(row['original_AV_replay_bitwise_equal'] is True and row['FP32_centered_controls'] == 1,
                'Actual tiny replay/control failed')
        audit_identity(row['identity'])
    return expected


def publication(attempt):
    require(rawref(PUB)['sha256'] == PUB_SHA and rawref(CORRECTION)['sha256'] == CORRECTION_SHA,
            'Fixed original/correction publication receipts differ')
    proof, correction = read(PUB), read(CORRECTION)
    require(proof['schema'] == 'model_v3_actual_publication_v11'
        and proof['status'] == 'EXACT_LOCAL_TREE_PUBLISHED_REF_READ_BACK'
        and proof['repository'] == 'mint258/MFM' and proof['branch'] == 'model-v3'
        and proof['created_public_commit'] == proof['actual_ref_readback'] == PUBLIC_COMMIT
        and proof['source_manifest_sha256'] == PIN and proof['attention_AV_executed_before_publication'] is False
        and proof['update_ref_success'] is True and proof['force'] is False
        and proof['checker_actual_state'] == 'COMPLETED' and proof['checker_actual_exit'] == '0:0'
        and proof['candidate_adopted'] is False and proof['main_modified'] is False and proof['recipe_frozen'] is False,
        'Actual pre-execution publication identity differs')
    require(correction['schema'] == 'model_v3_publication_v11_payload_SHA_transcription_correction_v1'
        and correction['status'] == 'MACHINE_HASH_CORRECTION_ONLY_ORIGINAL_RETAINED'
        and correction['original_publication_receipt'] == rawref(PUB)
        and correction['source_manifest'] == rawref(S/'source_pins_v1.json')
        and correction['original_receipt_modified'] is False
        and correction['scientific_source_or_experiment_changed'] is False,
        'Independent machine correction chain differs')
    require(correction['original_claimed_payload_sha256'] == proof['payload_sha256']
        and correction['original_claimed_SHA_length'] == len(proof['payload_sha256']) == 65,
        'Original malformed65-character checksum must remain explicit')
    payload_ref = correction['actual_payload']
    payload = bound(payload_ref)
    require(payload_ref['path'] == str(N/'reporting_publication_payload_v11.json')
        and payload_ref['bytes'] == proof['payload_bytes']
        and payload_ref['sha256'] == correction['corrected_payload_sha256']
        and len(payload_ref['sha256']) == 64, 'Actual machine payload SHA differs')
    require(payload['local_commit'] == proof['local_commit'] == correction['local_commit']
        and payload['local_tree'] == proof['local_and_api_tree'] == correction['local_and_api_tree']
        and payload['parent_public_commit'] == proof['expected_previous_public_commit']
        and correction['created_public_commit'] == correction['actual_ref_readback'] == PUBLIC_COMMIT,
        'Payload/local/public exact-tree mapping differs')
    start = datetime.fromisoformat(attempt['started_utc'])
    require(start.tzinfo is not None, 'Actual submission start must carry timezone')
    started_unix = start.timestamp()
    proof_mtime_ns = PUB.stat().st_mtime_ns
    payload_mtime_ns = Path(payload_ref['path']).stat().st_mtime_ns
    require(proof_mtime_ns/1e9 <= started_unix and payload_mtime_ns/1e9 <= started_unix,
            'Root stored publication proof/payload was not written before actual attempt start')
    return {'original_proof':rawref(PUB), 'machine_SHA_correction':rawref(CORRECTION),
        'actual_payload':payload_ref, 'public_commit':PUBLIC_COMMIT,
        'local_commit':proof['local_commit'], 'local_and_API_tree':proof['local_and_api_tree'],
        'proof_file_mtime_ns':proof_mtime_ns, 'payload_file_mtime_ns':payload_mtime_ns,
        'actual_attempt_started_utc':attempt['started_utc'],
        'Root_file_mtimes_precede_attempt':True, 'timestamps_are_GitHub_server_times':False,
        'original_invalid_payload_SHA_length':65, 'invalid_original_not_silently_normalized':True,
        'correction_after_submission':correction['created_unix'] > started_unix,
        'correction_retroactively_registers_experiment':False,
        'GitHub_live_readback_performed_by_this_closer':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=N/'attention_AV_4521641_Root_metadata_closure_v1.json')
    args = parser.parse_args()
    require(os.getuid() == 1278 and socket.gethostname() == 'sonmi', 'Root login metadata context required')
    require(args.output.parent == N and not args.output.exists(), 'Fresh explicit N output required')
    require(rawref(S/'source_pins_v1.json')['sha256'] == PIN, 'Exact frozen source manifest differs')
    pins = read(S/'source_pins_v1.json'); request = read(S/'execution_request_v1.json')
    require(pins['schema'] == 'model_v3_attention_av_diagnostic_launch_source_pins_v1'
        and len(pins['files']) == 9 and len(pins['protected_dependencies']) == 270,
        'Frozen AV source membership differs')
    expected = {x['path']:x for x in request['source_refs']+pins['files']+pins['protected_dependencies']}
    expected[str(S/'source_pins_v1.json')] = rawref(S/'source_pins_v1.json')
    before, after = read(D/'sources_before.json'), read(D/'sources_after.json')
    require(len(before) == 280 and before == after == expected
        and sum(x['bytes'] for x in before.values()) <= 16<<20, 'Recorded complete source graph/stability differs')
    for path,leaf in before.items():
        require(leaf['path'] == path and rawref(path) == leaf, 'Current source drift: '+path)
    attempt_path = O/'attention_AV_centering_GPU_v1_attempt1.json'
    attempt = read(attempt_path)
    require(attempt['schema'] == 'model_v3_attention_av_diagnostic_launch_submission_v1'
        and attempt['status'] == 'SUBMITTED' and attempt['job_id'] == JOB
        and attempt['bindings']['MODEL_V3_NUMERIC_GPU_LAUNCH_PINS_SHA'] == PIN
        and attempt['bindings']['MODEL_V3_EXPECTED_NODE'] == 'compute-0-21'
        and attempt['bindings']['MODEL_V3_GPU_UUID'] == UUID
        and attempt['inputs']['launch_source_pins'] == rawref(S/'source_pins_v1.json'),
        'Actual source-bound Root submission differs')
    public = publication(attempt)
    complete = read(D/'COMPLETE.json')
    require(complete['schema'] == 'model_v3_attention_av_diagnostic_closure_v1'
        and complete['status'] == 'LOCAL_DIAGNOSTIC_COMPLETE' and complete['failure'] is None
        and complete['counts'] == COUNTS and complete['sources_before_after_equal'] is True
        and complete['physics_acceptance'] is False, 'Actual AV diagnostic closure differs')
    result = bound(complete['result'])
    require(Path(complete['result']['path']) == D/'ANALYSIS_RESULT.json'
        and result['schema'] == 'model_v3_attention_av_centering_diagnostic_result_v1'
        and result['status'] == 'LOCAL_DIAGNOSTIC_COMPLETE'
        and result['scope'] == 'ACTUAL1492_FP32_COUPLED_ATTENTION_FIXED_INPUTS_ONLY'
        and result['case_count'] == len(result['cases']) == 48 and result['counts'] == COUNTS
        and result['physics_acceptance'] is False and result['production_centered_model_executed'] is False
        and result['F64_encoder_recomputed'] is False
        and result['NativeRuntimeDense_bf16_training_dropout_covered'] is False
        and result['cache_layout_restored_but_pointer_relocated'] is True,
        'Complete unselected local diagnostic result differs')
    protocol = bound(result['protocol'])
    require(result['protocol'] == pins['analysis_protocol']
        and protocol['expected_cases'] == 48 and protocol['expected_encoder_forwards'] == 192
        and protocol['expected_AV_observations'] == 1152 and protocol['FP64_encoder_forwards'] == 0,
        'Exact preregistered protocol differs')
    ids = request['expected_case_ids']
    require(len(ids) == len(set(ids)) == 48 and [x['case_id'] for x in result['cases']] == ids,
            'Canonical full48 identity/order differs')
    gate = read(D/'FP32_REPLAY_GATE.json')
    gate_counts = {**COUNTS, 'original_AV_replays':0, 'centered_controls':0,
                   'FP64_Rraw_calls':0, 'FP64_Rnorm_calls':0, 'FP64_Cexact_calls':0}
    require(gate['status'] == 'ALL48_192_ROLES_BITWISE_MATCH_ACTUAL1492'
        and gate['counts'] == gate_counts and gate['AV_controls_started_before_gate'] is False
        and gate['tiny_controls_separate'] is True and gate['source_capture'] == protocol['capture_complete']
        and 0 < gate['CPU_cache_payload_bytes'] <= protocol['CPU_cache_payload_cap_bytes'],
        'Global capture-enabled192 H0/1152 AV gate sequencing differs')
    bound(gate['source_capture'])
    tiny = read(D/'INLINE_TINY_CONTROLS.json')
    require(tiny == result['tiny_controls'], 'Separate tiny sidecar/result differ')
    tiny_counts = tiny_check(tiny)
    comparison_count, operation_count, identity_count = 0, 0, 0
    role_refs, case_refs = [], []
    for ordinal,item in enumerate(result['cases']):
        require(Path(item['result']['path']) == D/('AV_case%02d.json' % ordinal), 'Case path differs')
        case = bound(item['result'])
        require(case['schema'] == 'model_v3_AV_local_case_v1' and case['case_id'] == item['case_id']
            and case['operation_count'] == len(case['observations']) == 24
            and case['physics_acceptance'] is False, 'Complete per-case24 observations required')
        replay = read(D/('replay_case%02d.json' % ordinal))
        nodes = 88 if replay['case']['views'] == 'two' else 132
        graphs = 6 if nodes == 88 else 9
        require(replay['case_id'] == item['case_id'] and replay['encoder_forward_shapes'] == [[nodes,512]]*4,
                'Actual coupled full-view encoder layout differs')
        expected_class = 'DenseGeoSelfAttention' if replay['case']['distance_bias'] == 'C1-0' else 'SharedPairAttention'
        for role in range(4):
            path = D/('replay_case%02d_role%d.json' % (ordinal,role))
            observed = read(path)
            require(observed['case_id'] == item['case_id'] and observed['role'] == role
                and observed['captured_AV'] == 6
                and [x['name'] for x in observed['comparisons']] ==
                    ['actual_bank_H0','actual_bank_pos','actual_bank_batch'],
                'Actual capture-enabled role/source population differs')
            for comparison in observed['comparisons']:
                require(comparison['bitwise_equal'] is True and comparison['actual'] == comparison['original1492'],
                        'Recorded original1492 bitwise comparison failed')
                comparison_count += 1
            role_refs.append(rawref(path))
        for position,row in enumerate(case['observations']):
            require(row['case_id'] == item['case_id'] and row['role'] == position//6 and row['layer'] == position%6
                and row['class'] == expected_class and row['capture']['class'] == expected_class
                and row['capture']['layer'] == position%6 and row['capture']['matmuls'] == 2
                and row['original_AV_replay_bitwise_equal'] is True, 'Actual1152 AV pairing/replay identity differs')
            require(all(row[key] == 1 for key in ('FP32_centered_controls','FP32_original_AV_replays',
                        'FP64_Rraw_calls','FP64_Rnorm_calls','FP64_Cexact_calls')),
                    'Exactly one declared control/reference per AV required')
            require(row['physics_acceptance'] is False and row['production_centered_forward_executed'] is False
                and row['NativeRuntimeDense_or_bf16_or_training_dropout_covered'] is False
                and row['effective_dropout_disabled'] is True and row['all_masked_valid_queries'] == 0
                and row['capture']['radius_mask_enabled'] is False,
                'Declared valid-population/dropout/scope differs')
            require(row['flags'] == row['capture']['arithmetic_flags'] ==
                {'autocast':False,'tf32':False,'matmul_precision':'highest','deterministic':False},
                'Original FP32 capture/replay policy differs')
            heads = row['capture']['headers']
            for name in ('p','v','logits','output'):
                h = heads[name]
                shape = [graphs,8,32,32 if name in ('p','logits') else 64]
                require(h['dtype'] == 'torch.float32' and h['device'] == 'cuda:0' and h['shape'] == shape
                    and len(h['stride']) == 4 and all(type(x) is int and x >= 0 for x in h['stride'])
                    and type(h['storage_offset']) is int and h['storage_offset'] >= 0,
                    'Recorded original operand layout/dtype/device differs')
            require(row['valid_query_rows'] == nodes*8 and row['all_query_rows'] == graphs*32*8
                and row['padded_query_rows'] == (graphs*32-nodes)*8
                and len(row['anchor_indices']) == graphs
                and all(type(x) is int and 0 <= x < 32 for x in row['anchor_indices']),
                'Native valid/padded query and mask-only anchor population differs')
            require(row['same_component']['population'] ==
                'original_minus_Rnorm absolute argmax over all valid queries/head/components'
                and len(row['same_component']['index']) == 4,
                'Fixed same-component population differs')
            audit_identity(row['identity'])
            identity_count += 1; operation_count += 1
        case_refs.append(item['result'])
    require(comparison_count == 576 and operation_count == identity_count == 1152
        and len(role_refs) == 192, 'Complete192/1152 metadata comparison population differs')
    sup_path = O/'attention_AV_centering_GPU_v1_supervisor_4521641.json'
    sup = read(sup_path)
    require(sup['job_id'] == JOB and sup['status'] == 'COMPLETED' and sup['exit_code'] == 0
        and sup['first_failure'] is None and sup['retirement'] is None
        and sup['remaining_recorded_processes_before_retirement'] == []
        and sup['private_storage_cleanup_errors'] == [] and sup['foreign_gpu_processes_signalled'] is False
        and sup['supervisor_source_sha256'] == request['supervisor_source']['sha256']
        and sup['gpu_uuid'] == UUID and sup['output_budget_bytes'] == 2<<30
        and sup['child_output_budget_bytes'] == (2<<30)-(96<<20)
        and 0 <= sup['last_output_bytes'] < (2<<30)-(16<<20), 'Actual original GPU supervision closure differs')
    private = sup['private_storage_final']
    require(private['budget_bytes'] == 2<<30 and private['first_sampling_failure'] is None
        and 0 <= private['sampled_max_bytes'] <= 2<<30 and private['exact_peak'] is False,
        'Actual private supervision closure differs')
    command = sup['command']
    require(command[3] == str(S/'run_av_diagnostic.py')
        and command[command.index('--request')+1] == str(S/'execution_request_v1.json')
        and command[command.index('--request-sha256')+1] == rawref(S/'execution_request_v1.json')['sha256']
        and command[command.index('--output-root')+1] == str(D), 'Actual supervised command/source differs')
    uuid = read(D/'CUDA_UUID_ADMISSION.json')
    require(uuid['job_id'] == JOB and uuid['node'] == 'compute-0-21' and uuid['gpu_uuid'] == UUID,
            'Actual CUuuid admission differs')
    worker_path = O/'attention_AV_centering_GPU_v1_launch_v1_worker_4521641.json'
    worker = read(worker_path)
    require(worker['job_id'] == JOB and worker['status'] == 'CHILD_RETURNED' and worker['child_exit_code'] == 0
        and worker['inputs'] == attempt['inputs'] and worker['submission_receipt'] == rawref(attempt_path)
        and worker['worker_sacct_queries'] == worker['worker_quota_queries'] == 0,
        'Actual source-bound launch worker closure differs')
    allocation = worker['actual_allocation_identity']
    require(allocation['job_id'] == JOB and allocation['uid'] == 1278 and allocation['node'] == 'compute-0-21'
        and allocation['cpus_per_task'] == 16 and allocation['memory_per_node_MiB'] == 32768
        and worker['public_GPU_lock']['fd'] == 9 and worker['public_GPU_lock']['uid'] == 1278
        and worker['public_GPU_lock']['kernel_exclusive_lock_acquired_or_revalidated'] is True,
        'Actual allocation/public-fd9 authority differs')
    census = worker['closed_control_output_census']
    require(census['output_root'] == str(D) and census['cap_bytes'] == 2<<30
        and census['conservative_total_bytes'] <= 2<<30
        and census['conservative_worker_receipt_allowance_bytes'] == 2<<20
        and census['is_live_monitor'] is False and census['uses_original_owned_output_bytes'] is True,
        'Original final whole-control census differs')
    argv = ['sacct','-X','-n','-P','-j',JOB,
            '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,AllocTRES']
    raw = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    rows = [line.split('|') for line in raw.stdout.splitlines() if line.strip()]
    require(raw.returncode == 0 and len(rows) == 1 and len(rows[0]) == 8
        and rows[0][:4] == [JOB,'zixiao','COMPLETED','0:0'] and int(rows[0][4]) == 75
        and int(rows[0][5]) == 16 and rows[0][6] == 'compute-0-21', 'Actual raw parent sacct differs')
    file_bytes, file_count = 0, 0
    for path in D.rglob('*'):
        info = path.lstat()
        require(info.st_uid == os.getuid() and not stat.S_ISLNK(info.st_mode), 'Output census ownership/link differs')
        if stat.S_ISDIR(info.st_mode):
            continue
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'Output census ordinary file differs')
        file_bytes += info.st_size; file_count += 1
    require(file_bytes <= protocol['compact_output_cap_bytes'] == 128<<20
        and file_bytes <= sup['child_output_budget_bytes'], 'Current stat-only output exceeds original limits')
    require(read(D/'sources_after.json') == after and all(rawref(path) == leaf for path,leaf in before.items()),
            'Sources changed during Root metadata closure')
    role_digest = hashlib.sha256(json.dumps(role_refs,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    outcome = {'schema':'model_v3_attention_AV_4521641_Root_metadata_closure_v1',
        'status':'ROOT_METADATA_VERIFIED_LOCAL_DIAGNOSTIC_ONLY',
        'created_utc':datetime.now(timezone.utc).isoformat(), 'producer_source':rawref(__file__), 'job_id':JOB,
        'source_manifest':rawref(S/'source_pins_v1.json'), 'sources_recorded_before_after_equal_and_current':True,
        'declared_own_files':9, 'declared_protected_dependencies':270,
        'unique_source_refs_including_manifest':280, 'source_ref_bytes':sum(x['bytes'] for x in before.values()),
        'public_preregistration':public, 'complete':rawref(D/'COMPLETE.json'), 'result':complete['result'],
        'case_results':case_refs, 'FP32_replay_gate':rawref(D/'FP32_REPLAY_GATE.json'),
        'actual_capture_enabled_roles_bitwise_matched':192, 'individual_H0_pos_batch_bitwise_comparisons':576,
        'ordered192_role_metadata_ref_list_sha256':role_digest,
        'scientific_counts':COUNTS, 'actual_original_AV_replay_bitwise_records':operation_count,
        'recorded_independent_identity_audit_records':identity_count,
        'tiny_controls':rawref(D/'INLINE_TINY_CONTROLS.json'), 'tiny_counts_separate':tiny_counts,
        'submission':rawref(attempt_path), 'worker':rawref(worker_path), 'supervisor':rawref(sup_path),
        'CUuuid_admission':rawref(D/'CUDA_UUID_ADMISSION.json'),
        'recorded_original_final_census':census,
        'whole_output_ceiling_bytes':2<<30, 'private_ceiling_bytes':2<<30,
        'supervisor_last_whole_output_observation_bytes':sup['last_output_bytes'],
        'private_sampled_max_bytes':private['sampled_max_bytes'], 'private_exact_peak_claimed':False,
        'current_output_regular_file_stat_census':{'files':file_count,'bytes':file_bytes,'payloads_opened':False},
        'raw_accounting':{'argv':argv,'returncode':raw.returncode,'stdout':raw.stdout,'stderr':raw.stderr,
            'stdout_sha256':hashlib.sha256(raw.stdout.encode()).hexdigest(),
            'stderr_sha256':hashlib.sha256(raw.stderr.encode()).hexdigest()},
        'model_project_or_tensor_libraries_imported':False,
        'SDK_NPZ_or_scientific_CSV_opened_or_rehashed':False,
        'AV_scientific_error_metrics_aggregated':False, 'tensor_bitwise_or_identity_independently_recomputed':False,
        'recorded_comparison_truth_verified':True, 'current_process_table_queried':False,
        'cache_layout_restored_not_original_pointer':True, 'centered_V_layout_identity_independently_proved':False,
        'FP64_encoder_recomputed':False, 'production_centered_model_executed':False,
        'NativeRuntimeDense_bf16_or_training_dropout_covered':False,
        'FP32_physics_acceptance_or_scientific_adoption':False}
    encoded = (json.dumps(outcome,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    require(len(encoded) < 64<<10, 'Bounded Root closure metadata required')
    with args.output.open('xb') as stream:
        stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({'status':outcome['status'],'output':rawref(args.output)}))


if __name__ == '__main__':
    main()
