"""Same-source735 recovery evidence. No fixed deadline, retry limit, or READY claim."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import time
from .kernel import observe_row, physical, require


def file_reference(path):
    path = Path(path)
    h = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
            size += len(block)
    return dict(path=str(path.resolve()), bytes=size, sha256=h.hexdigest())


def run(args):
    job = os.environ.get('SLURM_JOB_ID')
    require(job and job.isdecimal(), 'Run original DATA only within an actual Slurm allocation')
    require(int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) >= args.workers >= 16,
            'At least16 actual allocated CPUs and workers required')
    source = Path(args.diagnosis)
    require(not source.is_symlink() and source.is_file(), 'Regular original diagnosis file required')
    before = source.stat()
    ref = file_reference(source)
    require(ref['sha256'] == args.expected_sha256 and ref['bytes'] == args.expected_bytes,
            'Original whole diagnosis byte/hash pin mismatch')
    with source.open(encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream]
    require(len(rows) == args.expected_rows == 735, 'Complete original735 required, no sampling')
    locators = [physical(row['norm_observation']['source']) for row in rows]
    require(len(set(locators)) == len(locators), 'Original physical locators must be unique')
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    counts = Counter()
    worker_pids = set()
    rules = {}
    ledger = out / 'all735_original_recovery_evidence.DATA.jsonl'
    with ProcessPoolExecutor(max_workers=args.workers) as executor, ledger.open('x', encoding='utf-8') as stream:
        for result in executor.map(observe_row, rows, chunksize=8):
            worker_pids.add(result['worker_pid'])
            counts['physical_source_rows'] += 1
            counts['proposed_covered_rows' if result['proposed_exclusion_coverage'] else 'HOLD_rows'] += 1
            counts['remaining_HOLD_variants'] += result['hold_count']
            for observation in result['variant_observations']:
                counts['variant:' + observation['disposition']] += 1
                if observation['disposition'] == 'CONSERVATIVE_NON_H_ATOM_LOWER_BOUND':
                    key = json.dumps(observation['bound'], separators=(',', ':'))
                    rules.setdefault(key, []).append(dict(locator=result['locator'], source_field=observation['source_field']))
            stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    rules_file = out / 'proposed_lower_bounds.DATA.jsonl'
    with rules_file.open('x', encoding='utf-8') as stream:
        for i, (bound, origins) in enumerate(sorted(rules.items())):
            stream.write(json.dumps(dict(rule_id='coconut735:' + str(i), dataset='coconut',
                kind='NON_H_ATOM_COUNT_LOWER_BOUND', bound=json.loads(bound), origins=origins,
                accepted_for_filtering=False, original_graph_identity_resolution='UNKNOWN_UNCHANGED'),
                ensure_ascii=False, separators=(',', ':')) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    require(file_reference(source) == ref and source.stat().st_ino == before.st_ino and
            source.stat().st_mtime_ns == before.st_mtime_ns, 'Original diagnosis changed during recovery')
    receipt = dict(schema='COCONUT735_RECOVERY_EVIDENCE_RECEIPT_V1',
        status='CANDIDATE_EVIDENCE_COMPLETE_NOT_ACCEPTED_FOR_EXCLUSION', job_id=job,
        uid=os.getuid(), node=os.uname().nodename, input=ref, counts=dict(counts),
        physical_rows_preserved=735, actual_worker_pids=sorted(worker_pids), original_graph_identities_repaired=False,
        candidate_filtering_performed=False, candidate_pool_released=False,
        all_source_decontamination_READY=False, new_key_QM_UFF_calls=0,
        outputs=dict(ledger=file_reference(ledger), lower_bounds=file_reference(rules_file)),
        wall_seconds=time.monotonic()-start,
        remaining_actions=['Resolve every HOLD from the same original source or exact official identity evidence',
            'Measure conservative-veto impact on the actual complete candidate pool',
            'Independently adopt sound complete nondegenerate coverage before all11 filtering'])
    receipt_path = out / 'receipt.json'
    with receipt_path.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(dict(receipt=file_reference(receipt_path), counts=dict(counts)), sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnosis', required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--expected-bytes', type=int, required=True)
    parser.add_argument('--expected-rows', type=int, default=735)
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--output', required=True)
    run(parser.parse_args())


if __name__ == '__main__':
    main()
