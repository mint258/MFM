"""Remove redundant closed TEST shards, retaining a complete reviewable worker sample."""
import json, os, stat, time
from pathlib import Path

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
bench=ROOT/'wp4_storage_benchmark/job_4513016'
summary=json.loads((bench/'benchmark_summary.json').read_text())
assert summary['status']=='TEST_LOSSLESS_STORAGE_BENCHMARK_COMPLETE' and not summary['issues']
assert (ROOT/'logs/wp4_storage_benchmark_4513016.exitcode').read_text().strip()=='0'
assert (ROOT/'logs/wp4_archive_scope_projection_4513035.exitcode').read_text().strip()=='0'
base=(bench/'TEST_parquet').resolve()
assert base.is_relative_to(ROOT.resolve())
removed=[]
for number in range(1,16):
    folder=base/f'worker_{number:02d}'
    if not folder.exists():
        continue
    assert not folder.is_symlink() and folder.resolve().parent==base
    for path in sorted(folder.glob('*.parquet')):
        info=path.lstat()
        assert stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid()
        assert path.resolve().parent==folder
        removed.append({'path':str(path),'bytes':info.st_size})
        path.unlink()
    if not any(folder.iterdir()):
        folder.rmdir()
report={'UTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'bytes_removed':sum(item['bytes'] for item in removed),'files_removed':len(removed),
        'removed':removed,'retained_review_sample':str(base/'worker_00'),
        'all_original_native_results_and_raw_retained':True,
        'full_roundtrip_evidence_and_prototype_manifest_retained':True,
        'rebuild_script':str(ROOT/'scripts/wp4_storage_benchmark.py')}
(ROOT/'reports/test_storage_cleanup.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({key:report[key] for key in ('bytes_removed','files_removed','retained_review_sample')}))
