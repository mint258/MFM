"""Publish existing closed scientific results and authentic terminal metadata."""
import json, os, socket, time
from pathlib import Path
from prepare import ROOT, save, sha

def main():
    assert os.getuid() == 1278 and socket.gethostname().split('.')[0] == 'sonmi'
    summary_path = ROOT / 'reports/pilot_summary.json'
    result = json.loads(summary_path.read_text())
    accounting = json.loads((ROOT / 'reports/all_work_accounting.json').read_text())
    expected = [g['receipt']['job_id'] for g in result['groups']]
    expected += [result['reproduction100']['generation_job_id'], result['reproduction100']['comparison_job_id']]
    assert len(set(expected)) == 7
    actual = {jid: accounting['parent_jobs'][jid] for jid in expected}
    assert all(r['State'] == 'COMPLETED' and r['ExitCode'] == '0:0' and r['User'] == 'zixiao' for r in actual.values())
    assert result['pilot_molecules'] == 10000 and sum(result['status_counts'].values()) == 10000
    assert result['reproduction100']['status'] == 'PASS'
    assert sha(ROOT / 'scripts/sprime_v6.py') == result['source_sha256']
    assert not (ROOT / 'full/work.sqlite').exists(), 'Unexpected full queue: this acceptance is pilot-only'
    accepted = {'status': 'PILOT_SUBSET_CLOSED_REPRODUCTION100_PASS', 'timestamp': time.time(),
        'stage': 'pilot_v6', 'molecules': 10000, 'source_S_conformers': sum(g['pm7_total'] for g in result['groups']),
        'sprime_conformers': result['pilot_conformers'], 'source_sha256': result['source_sha256'],
        'pilot_summary_sha256': sha(summary_path), 'guide_sha256': result['guide_sha256'],
        'population_binding_sha256': sha(ROOT / 'prepared/population_binding.json'),
        'reproduction100': result['reproduction100'], 'actual_completed_jobs': actual,
        'all_work_actual_allocated_core_hours': accounting['actual_core_hours_all_work'],
        'accounting_snapshot_timestamp': accounting['timestamp'],
        'full_run_status': result['status'], 'full_generation_submitted': False,
        'training_status': 'FROZEN_PROTOCOL_PATH_REQUIRED', 'B1_B3_submitted': False,
        'original_lmdb_written': False, 'new_lmdb_created': False,
        'scientific_verification_job_id': result['reproduction100']['comparison_job_id']}
    save(ROOT / 'reports/pilot_acceptance.json', accepted)
    report_names = ['pilot_summary.json', 'pilot_report.md', 'pilot_details.md', 'summary_report.md',
        'summary_report.pdf', 'sprime_pilot_geometry.png', 'sprime_pilot_geometry.svg',
        'pilot_reproduction100.json', 'pilot_acceptance.json', 'all_work_accounting.json',
        'full_run_review.md', 'full_run_review_sources.json', 'full_quota_preflight.json',
        'training_preparation.md', 'training_configuration_pending.json']
    reports = [{'path': str(ROOT / 'reports' / name), 'bytes': (ROOT / 'reports' / name).stat().st_size,
                'sha256': sha(ROOT / 'reports' / name)} for name in report_names]
    save(ROOT / 'reports/deliverables_sha_manifest.json', {'stage': 'pilot_v6',
        'scientific_data_verified_by_job': result['reproduction100']['comparison_job_id'],
        'data': result['sha_manifest'], 'reports': reports})
    print(json.dumps({k: accepted[k] for k in ['status', 'molecules', 'source_S_conformers',
        'sprime_conformers', 'all_work_actual_allocated_core_hours', 'full_run_status', 'training_status']}))

if __name__ == '__main__':
    main()
