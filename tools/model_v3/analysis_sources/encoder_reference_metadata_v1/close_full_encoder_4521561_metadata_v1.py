"""Root metadata closure only; no project imports, tensor loads, SDK reads or reruns."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess

B = Path('/share/home/zixiao/descriptor_analysis')
O = B/'runs/model_v3_20261025'
N = B/'runs/model_v3_20261026'
D = O/'full_encoder_FP64_GPU_v1_4521561'
S = N/'numeric_full_encoder_fp64_v1_source'
JOB = '4521561'
PIN = 'e14c0d33b8b0bb7ef5cd019e1ad1189bf97a2c8815af7c6e27025753f21fbefd'
UUID = 'GPU-c35f2434-9137-9723-1af5-dc69b6295243'
ALLOWED = {'.py', '.json', '.jsonl', '.md', '.sbatch'}

def require(value, message):
    if not value:
        raise ValueError(message)

def rawref(path, maximum=2<<20):
    path = Path(path).absolute()
    require(path.is_relative_to(B) and path.suffix in ALLOWED,
            'Only explicit project source/metadata may be opened')
    before = path.lstat()
    require(path == path.resolve(strict=True) and stat.S_ISREG(before.st_mode)
            and before.st_uid == os.getuid() and before.st_nlink == 1
            and before.st_size <= maximum, 'Owned bounded ordinary metadata required')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1<<20), b''):
            digest.update(block)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
            'Metadata changed while hashing')
    return {'path': str(path), 'bytes': before.st_size, 'sha256': digest.hexdigest()}

def read(path, maximum=2<<20):
    initial = rawref(path, maximum)
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    value = json.loads(Path(path).read_bytes(), object_pairs_hook=unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    require(rawref(path, maximum) == initial, 'Metadata changed while decoding')
    return value

def bound(value):
    require(set(value) == {'path', 'bytes', 'sha256'} and rawref(value['path']) == value,
            'Raw source/metadata reference differs')
    return read(value['path'])

def policy(value):
    require(value['effective_attention_radius'] is None and value['active_Gaussian_cutoff'] is None
            and value['Gaussian_center_range_is_cutoff'] is False
            and value['S_geometry_and_pair_head_FP64_covered'] is False
            and len(value['attention']) == 6
            and [x['layer'] for x in value['attention']] == list(range(6))
            and all(x['use_radius_mask'] is False for x in value['attention']),
            'Global fixed-matrix geometry scope differs')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=N/'full_encoder_FP64_GPU_4521561_Root_metadata_closure_v1.json')
    args = parser.parse_args()
    require(os.getuid() == 1278 and socket.gethostname() == 'sonmi', 'Actual Root login metadata context required')
    require(args.output.parent == N and not args.output.exists(), 'Fresh immediate N closure required')
    pins = read(S/'source_pins_v1.json')
    require(rawref(S/'source_pins_v1.json')['sha256'] == PIN, 'Exact frozen source manifest required')
    request = read(S/'execution_request_v1.json')
    before, after = read(D/'sources_before.json'), read(D/'sources_after.json')
    expected = {x['path']: x for x in request['source_refs']+pins['files']+pins['protected_dependencies']}
    expected[str(S/'source_pins_v1.json')] = rawref(S/'source_pins_v1.json')
    require(len(pins['files']) == 7 and len(pins['protected_dependencies']) == 260
            and len(before) == 268 and before == after == expected, 'Complete source graph membership/recorded stability differs')
    require(sum(x['bytes'] for x in before.values()) <= 16<<20, 'Source audit aggregate cap exceeded')
    for path, value in before.items():
        require(value['path'] == path and rawref(path) == value, 'Current source differs: '+path)
    complete = read(D/'COMPLETE.json')
    counts = {'FP32_full_encoder_returns': 192, 'FP64_full_encoder_returns': 192}
    require(complete['status'] == 'ANALYSIS_COMPLETE' and complete['failure'] is None
            and complete['counts'] == counts and complete['functional64_scientific_bank_calls'] == 192
            and complete['sources_before_after_equal'] is True and complete['scientific_adoption'] is False
            and complete['original1492_not_replaced'] is True, 'Actual analysis closure differs')
    result = bound(complete['result'])
    require(result['schema'] == 'model_v3_full_encoder_precision_analysis_result_v1'
            and result['status'] == 'ANALYSIS_COMPLETE' and result['scope'] == 'ACTUAL1492_INPUT_PRECISION_ANALYSIS_ONLY'
            and result['case_count'] == 48 and len(result['cases']) == 48 and result['counts'] == counts
            and result['functional64_scientific_bank_calls'] == 192 and result['scientific_adoption'] is False,
            'Actual complete analysis result differs')
    require(bound(result['protocol']) == bound(pins['analysis_protocol']), 'Analysis protocol reference differs')
    expected_ids = request['expected_case_ids']
    require(len(expected_ids) == len(set(expected_ids)) == 48
            and [x['case_id'] for x in result['cases']] == expected_ids, 'Original full48 order differs')
    gate = read(D/'FP32_REPLAY_GATE.json')
    require(gate['status'] == 'ALL48_192_ROLES_BITWISE_MATCH_ACTUAL1492'
            and gate['FP64_started_before_complete_replay_gate'] is False
            and gate['counts'] == {'FP32_full_encoder_returns': 192, 'FP64_full_encoder_returns': 0}, 'Replay sequencing gate differs')
    bound(gate['source_capture'])
    tiny = read(D/'INLINE_DEVICE_SELFCHECK.json')
    require(tiny['completed_tiny_dim4_one_layer_encoder_forwards'] == 12
            and tiny['completed_functional64_small_CPU_bank_calls'] == 4
            and tiny['completed_functional64_small_CUDA_bank_calls'] == 4
            and tiny['scientific_seed_or_initializer_changed'] is False
            and [x['kind'] for x in tiny['backbone_parity']] == ['C1-0', 'C1-a', 'C1-b']
            and all(x['tiny_legacy_FP32_bitwise_parity'] is True and x['tiny_FP64_dtype_and_replay'] is True
                    and x['shape'] == [3, 4] for x in tiny['backbone_parity'])
            and [(x['form'], x['pooling']) for x in tiny['unchanged_functional64_device_parity']] ==
                [('H1', 'sum'), ('H1', 'learned'), ('H2', 'sum'), ('H3', 'sum')]
            and all(0 <= x['maxabs_CPU_GPU_FP64'] <= 1e-10 for x in tiny['unchanged_functional64_device_parity']),
            'Actual separate tiny controls differ')
    comparison_count = 0
    case_refs = []
    for ordinal, item in enumerate(result['cases']):
        case = bound(item['result'])
        require(Path(item['result']['path']) == D/('reference_case%02d.json' % ordinal)
                and case['case_id'] == item['case_id'], 'Reference case raw binding differs')
        replay = read(D/('replay_case%02d.json' % ordinal))
        nodes = 88 if replay['case']['views'] == 'two' else 132
        require(replay['case_id'] == item['case_id'] and replay['encoder_forward_shapes'] == [[nodes,512]]*4
                and case['reference_physical_input_nodes_per_role'] == [nodes]*4
                and case['reference_encoder_input_was_clean44_only'] is False
                and case['canonical_PD_nodes_per_role'] == 44 and case['actual_input_only'] is True
                and case['ideal_or_polar_coordinate_counterfactual'] is False
                and case['S_geometry_or_pair_head_FP64_validated'] is False,
                'Full physical/canonical output scope differs')
        policy(case['original_actual_geometry_policy']); policy(case['reference_actual_geometry_policy'])
        require(len(case['reference_actual_layer_masks']) == 4 and len(case['stage_metrics']) == 54
                and len(case['terminal_observations']) == 9, 'Case stage/terminal coverage differs')
        h0 = case['FP64_clean_H0']
        require(set(h0['arrays']) == {'role%d_clean_H0' % role for role in range(4)}
                and all(x['dtype'] == 'torch.float64' and x['shape'] == [44,512] and x['bytes'] == 180224
                        for x in h0['arrays'].values()), 'Recorded F64 clean-H0 headers differ')
        # Deliberately do NOT open or rehash h0['file'] (NPZ); the recorded ref is provenance only.
        for role in range(4):
            observed = read(D/('replay_case%02d_role%d.json' % (ordinal, role)))
            require(observed['case_id'] == item['case_id'] and observed['role'] == role
                    and set(observed['stage_dtypes']) == {'embedding', 'out_norm', 'packed_H0', *('layer%d' % i for i in range(6))}
                    and set(observed['stage_dtypes'].values()) == {'torch.float32'}, 'FP32 stage coverage/dtype differs')
            policy(observed['actual_geometry_policy'])
            names = ['actual_bank_H0','actual_bank_pos','actual_bank_batch','canonical_clean_H0']
            require([x['name'] for x in observed['comparisons']] == names, 'Explicit replay comparisons differ')
            for comparison in observed['comparisons']:
                require(comparison['bitwise_equal'] is True and comparison['actual'] == comparison['original1492'],
                        'Recorded replay comparison fails')
                comparison_count += 1
        case_refs.append(item['result'])
    sup_path = O/'full_encoder_FP64_GPU_v1_supervisor_4521561.json'
    sup = read(sup_path)
    require(sup['job_id'] == JOB and sup['status'] == 'COMPLETED' and sup['exit_code'] == 0
            and sup['first_failure'] is None and sup['retirement'] is None
            and sup['remaining_recorded_processes_before_retirement'] == []
            and sup['private_storage_cleanup_errors'] == [] and sup['foreign_gpu_processes_signalled'] is False
            and sup['supervisor_source_sha256'] == request['supervisor_source']['sha256']
            and sup['gpu_uuid'] == UUID and sup['output_budget_bytes'] == 2<<30
            and sup['child_output_budget_bytes'] == (2<<30)-(96<<20)
            and 0 <= sup['last_output_bytes'] < (2<<30)-(16<<20), 'Actual GPU supervisor closure/budget differs')
    private = sup['private_storage_final']
    require(private['budget_bytes'] == 2<<30 and private['first_sampling_failure'] is None
            and 0 <= private['sampled_max_bytes'] <= 2<<30, 'Actual private storage closure differs')
    command = sup['command']
    require(command[3] == str(S/'analyze_encoder_precision_v1.py')
            and command[command.index('--request')+1] == str(S/'execution_request_v1.json')
            and command[command.index('--request-sha256')+1] == rawref(S/'execution_request_v1.json')['sha256']
            and command[command.index('--output-root')+1] == str(D), 'Actual supervised argv differs')
    attempt = read(O/'full_encoder_FP64_GPU_v1_attempt1.json')
    require(attempt['job_id'] == JOB and attempt['status'] == 'SUBMITTED'
            and attempt['bindings']['MODEL_V3_NUMERIC_GPU_LAUNCH_PINS_SHA'] == PIN
            and attempt['bindings']['MODEL_V3_GPU_UUID'] == UUID
            and attempt['bindings']['MODEL_V3_EXPECTED_NODE'] == 'compute-0-21', 'Actual submission binding differs')
    uuid = read(D/'CUDA_UUID_ADMISSION.json')
    require(uuid['job_id'] == JOB and uuid['gpu_uuid'] == UUID and uuid['node'] == 'compute-0-21', 'Actual CUuuid admission differs')
    argv = ['sacct','-X','-n','-P','-j',JOB,'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,AllocTRES']
    raw = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    rows = [line.split('|') for line in raw.stdout.splitlines() if line.strip()]
    require(raw.returncode == 0 and len(rows) == 1 and rows[0][:4] == [JOB,'zixiao','COMPLETED','0:0']
            and int(rows[0][4]) == 131 and int(rows[0][5]) == 16 and rows[0][6] == 'compute-0-21',
            'Actual raw parent accounting differs')
    current_bytes, files = 0, 0
    for path in D.rglob('*'):
        info = path.lstat()
        require(info.st_uid == os.getuid() and not stat.S_ISLNK(info.st_mode), 'Output census owner/link differs')
        if stat.S_ISDIR(info.st_mode):
            continue
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'Output census ordinary file differs')
        current_bytes += info.st_size; files += 1
    require(current_bytes <= sup['child_output_budget_bytes'], 'Current output census exceeds child ceiling')
    require(read(D/'sources_after.json') == after and all(rawref(path) == value for path,value in before.items()),
            'Sources changed during independent closure')
    outcome = {'schema':'model_v3_full_encoder_4521561_Root_metadata_closure_v1',
        'status':'ROOT_METADATA_VERIFIED_DIAGNOSTIC_ONLY','created_utc':datetime.now(timezone.utc).isoformat(),
        'producer_source':rawref(__file__),'job_id':JOB,'source_manifest':rawref(S/'source_pins_v1.json'),
        'sources_recorded_before_after_equal_and_current':True,'declared_manifest_leaves':267,
        'unique_source_refs_including_manifest':268,'source_refs_total_bytes':sum(x['bytes'] for x in before.values()),
        'complete':rawref(D/'COMPLETE.json'),'result':complete['result'],'case_results':case_refs,
        'FP32_replay_gate':rawref(D/'FP32_REPLAY_GATE.json'),'roles_bitwise_matched':192,
        'individual_bitwise_comparisons':comparison_count,'scientific_encoder_forward_counts':counts,
        'scientific_functional64_bank_calls':192,'tiny_controls':rawref(D/'INLINE_DEVICE_SELFCHECK.json'),
        'tiny_encoder_forward_count':12,'tiny_CPU_bank_calls':4,'tiny_CUDA_bank_calls':4,
        'supervisor':rawref(sup_path),'submission':rawref(O/'full_encoder_FP64_GPU_v1_attempt1.json'),
        'raw_accounting':{'argv':argv,'returncode':raw.returncode,'stdout':raw.stdout,'stderr':raw.stderr,
            'stdout_sha256':hashlib.sha256(raw.stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(raw.stderr.encode()).hexdigest()},
        'whole_output_ceiling_bytes':2<<30,'private_ceiling_bytes':2<<30,
        'supervisor_last_whole_output_observation_bytes':sup['last_output_bytes'],
        'private_sampled_max_bytes':private['sampled_max_bytes'],'private_exact_peak_claimed':False,
        'current_output_stat_census':{'bytes':current_bytes,'files':files,'payloads_opened':False},
        'SDK_or_NPZ_or_model_payload_read':False,'NPZ_current_rehash_performed':False,
        'tensor_equality_independently_recomputed':False,'original_recorded_comparison_truth_verified':True,
        'GitHub_live_readback_performed':False,'numerical_attribution_recomputed':False,
        'original1492_not_replaced':True,'original1435_H0_reconstructed':False,
        'science_adoption_or_FP32_acceptance':False}
    encoded = (json.dumps(outcome,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    require(len(encoded) < 64<<10, 'Compact Root closure cap exceeded')
    with args.output.open('xb') as stream:
        stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({'status':outcome['status'],'output':rawref(args.output)}))

if __name__ == '__main__':
    main()
