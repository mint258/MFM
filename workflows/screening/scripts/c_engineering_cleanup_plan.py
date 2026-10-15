"""Metadata-only checked cleanup plan for completed C3 duplicate success archives.

Never deletes. Keep first round, every partial/infrastructure-failure round and
every molecule with any non-SUCCESS outcome. Scientific Parquet always stays.
Root applies any later cleanup only after exact own terminal job confirmation
and before/after full source SHA checks on the explicitly named archive paths.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import stat
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
NODES=ROOT/'c_engineering/nodes'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
    pending=Path(str(path)+'.pending');pending.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');pending.replace(path)

def ordinary_owned(path,root):
    path=Path(path);resolved=path.resolve(strict=True);info=path.lstat()
    if not resolved.is_relative_to(root.resolve()) or stat.S_ISLNK(info.st_mode) or info.st_uid!=os.getuid():return None
    if not stat.S_ISREG(info.st_mode):return None
    return info

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    parser.add_argument('--output',default=str(ROOT/'reports/c_engineering_cleanup_plan.json'));args=parser.parse_args()
    if args.check:ast.parse(Path(__file__).read_text());print(json.dumps({'status':'AST_PASS','files_deleted':False}));return 0
    eligible=[];preserved=[];reports=[]
    for report_path in sorted(NODES.rglob('node_probe_report.json')):
        probe=read(report_path);root=report_path.parent
        if not ordinary_owned(report_path,NODES):continue
        reports.append({'path':str(report_path),'sha256':sha(report_path),'job_id':probe['job_id']})
        for round_ in probe['rounds']:
            summary=round_.get('summary')
            if round_['round']==0 or round_['returncode']!=0 or not summary or summary.get('status')!='C3_NATIVE_NODE_ROUND_COMPLETE':
                preserved.append({'job_id':probe['job_id'],'round':round_['round'],'reason':'First, partial, missing or infrastructure-failure round'});continue
            for receipt in summary['receipts']:
                reference=receipt.get('archive');reason=None
                if receipt.get('status')!='COMPLETE_WITH_RECORDED_OUTCOMES':reason='Partial molecule'
                elif any(value for key,value in receipt.get('statuses',{}).items() if key!='SUCCESS'):reason='All failure, skip and timeout evidence retained'
                elif not reference:reason='No existing archive reference'
                if reason:
                    preserved.append({'job_id':probe['job_id'],'round':round_['round'],'molecule_id':receipt['molecule_id'],'reason':reason});continue
                path=Path(reference['path']);info=ordinary_owned(path,root)
                parquet=receipt.get('parquet',{});parquet_path=Path(parquet.get('path',''))
                if info is None or info.st_size!=reference['bytes'] or not ordinary_owned(parquet_path,root) or parquet_path.stat().st_size!=parquet['bytes']:
                    preserved.append({'job_id':probe['job_id'],'round':round_['round'],'molecule_id':receipt['molecule_id'],'reason':'Owned path/size closure unavailable'});continue
                eligible.append({'job_id':probe['job_id'],'node':probe['hostname'],'round':round_['round'],
                    'molecule_id':receipt['molecule_id'],'path':str(path),'bytes':info.st_size,
                    'recorded_sha256':reference['sha256'],'current_inode':info.st_ino,'current_mtime_ns':info.st_mtime_ns,
                    'scientific_Parquet_preserved':parquet,
                    'requires_final_sacct_parent_terminal_and_no_live_job_before_apply':True,
                    'requires_actual_SHA256_match_before_delete':True})
    report={'status':'C3_METADATA_CLEANUP_PLAN_ONLY','script_sha256':sha(__file__),'created_epoch':time.time(),
        'source_closed_probe_reports':reports,'eligible_duplicate_all_success_archive_files':eligible,
        'planned_release_bytes':sum(item['bytes'] for item in eligible),'preserved':preserved,
        'files_deleted':False,'scientific_Parquet_deleted':False,'original_data_touched':False,
        'limits':'Only files under this exact new phase own nodes root; first complete/partial benchmark round, all molecule failures/timeouts/skips and scientific results always remain. Sampler and measurements retain archive recorded bytes/SHA. A later Root cleanup must preserve original receipt references via explicit retired-archive sidecar, not edit frozen source receipts.',
        'execution_note':'This plan performs lstat, ownership, disjoint-root and size checks only. It does not hash large archive contents or make a deletion-safe claim yet. Exact final job status and full SHA/inode/type checks are required in a bounded >=16CPU cleanup allocation before apply.'}
    output=Path(args.output).absolute()
    if not output.is_relative_to(ROOT/'reports'):raise ValueError('Own report only')
    save(output,report);print(json.dumps({'status':report['status'],'eligible_files':len(eligible),'planned_release_bytes':report['planned_release_bytes']}));return 0

if __name__=='__main__':raise SystemExit(main())
