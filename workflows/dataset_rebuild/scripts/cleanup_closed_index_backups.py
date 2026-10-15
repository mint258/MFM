"""Remove only two superseded new-run indices after full WP1 closure."""
import datetime, json, os
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
report=json.loads((ROOT/'wp1_results/screening_report.json').read_text())
if report['status']!='COMPLETE' or report['population']['records']!=15879477:
    raise RuntimeError('Full physical-source quality result must be closed first')
keep=[ROOT/'record_index.parquet',ROOT/'wp1_results/quality_annotations_v1.parquet',
      ROOT/'wp4_native_panel/pilot_panel.parquet']
if not all(path.is_file() for path in keep):raise RuntimeError('Current retained inputs missing')
targets=[ROOT/'record_index_existing_memberships.parquet',ROOT/'record_index_before_geometry_cache.parquet']
audit={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope':'Superseded derived indices in this new run; original LMDBs untouched',
    'closure_job_id':'4512824','preserved_current_inputs':[str(p) for p in keep],
    'reconstruction':'Original closed-core Parquet receipts plus unassigned_v2 index and archived scripts regenerate prior index stages.',
    'removed':[]}
for path in targets:
    if not path.exists():continue
    if path.is_symlink() or path.resolve().parent!=ROOT.resolve() or path.stat().st_uid!=os.getuid():
        raise RuntimeError('Unexpected backup path/type/ownership: '+str(path))
    stat=path.stat()
    audit['removed'].append({'path':str(path),'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns,
        'reason':'Complete current index retains all original memberships and all 8259 reassessed records; intermediate copies have no active job dependency.'})
for item in audit['removed']:
    Path(item['path']).unlink()
audit['removed_bytes']=sum(item['bytes'] for item in audit['removed'])
(ROOT/'reports/closed_index_backup_cleanup.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps({'removed_files':len(audit['removed']),'removed_bytes':audit['removed_bytes']}))
