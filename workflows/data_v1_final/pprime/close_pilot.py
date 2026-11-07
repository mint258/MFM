"""Close the pilot gates using actual parent Slurm accounting, without submitting work."""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

from common import load_config, reference, write_json


def assess(result, accounting_rows, config):
    job = str(result['runtime']['job_id'])
    rows = [row for row in accounting_rows if str(row.get('JobIDRaw', row.get('JobID'))) == job]
    if len(rows) != 1:
        raise ValueError('EXACTLY_ONE_ACTUAL_PARENT_ACCOUNTING_ROW_REQUIRED')
    parent = rows[0]
    if parent.get('User') != 'zixiao':
        raise ValueError('ACTUAL_ACCOUNTING_OWNER_MISMATCH')
    elapsed, cpus = int(parent['ElapsedRaw']), int(parent['AllocCPUS'])
    if elapsed < 0 or cpus < 16 or parent['NodeList'] != result['runtime']['node']:
        raise ValueError('ACTUAL_PARENT_RESOURCE_BINDING_MISMATCH')
    seconds = elapsed * cpus
    rate = seconds / 2000
    gates = {
        'parent_completed_zero': parent['State'] == 'COMPLETED' and parent['ExitCode'] == '0:0',
        'complete_2000_conformer_pilot': result['completed_records'] == 2000,
        'compute_closed_without_errors': result['status'] == 'PPRIME_PILOT_COMPUTE_CLOSED_AWAITING_PARENT_ACCOUNTING' and not result['failures'],
        'sixteen_workers_closed_and_joined': result['all_workers_joined'],
        'record_success_at_least_99_5_percent': result['record_success_rate'] >= config['minimum_success_rate'],
        'allocated_seconds_within_1_5x_wp5': rate <= config['maximum_allocated_core_seconds_per_conformer'],
    }
    return {'status': 'PPRIME_PILOT_GATES_PASS_ROOT_FULL_REVIEW_REQUIRED' if all(gates.values()) else 'PPRIME_PILOT_STOP_REPORT_USER_NO_FULL_SUBMISSION',
            'gates': gates, 'actual_parent': parent, 'allocated_core_seconds': seconds,
            'allocated_core_hours': seconds / 3600,
            'allocated_core_seconds_per_requested_conformer': rate,
            'denominator': 'all 2000 requested conformers, including failures',
            'raw_child_cpu_seconds_substituted_for_allocation': False,
            'post_pilot_anomaly_scan_still_required': not result.get('Pprime_outlier_scan_completed', False),
            'full_job_submitted': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--result', type=Path, required=True)
    p.add_argument('--sacct', type=Path, required=True,
                   help='Root-saved sacct -P: JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = json.loads(args.result.read_text())
    rows = list(csv.DictReader(io.StringIO(args.sacct.read_text()), delimiter='|'))
    report = assess(result, rows, load_config(args.config))
    report.update(result=reference(args.result), accounting=reference(args.sacct),
                  config=reference(args.config))
    write_json(args.output, report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
