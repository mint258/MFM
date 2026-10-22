"""Small, explicit, SHA-verified delivery archive; Sonmi file-transfer metadata only."""
import argparse,hashlib,json,os,socket,time,zipfile
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--packet-dir',type=Path,required=True);ap.add_argument('--visual-review',type=Path,required=True)
    ap.add_argument('--accounting',type=Path,required=True);ap.add_argument('--archive-receipt',type=Path,required=True);ap.add_argument('--service-retirement',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    for p in [a.packet_dir,a.visual_review,a.accounting,a.archive_receipt,a.service_retirement,a.output]:assert p.is_absolute() and p.is_relative_to(R)
    assert not a.output.exists() and a.output.suffix=='.zip'
    sources={};external=[]
    def add(p,expected=None):
        p=Path(p);assert p.is_absolute() and not p.is_symlink() and p.is_file();b=p.read_bytes();assert len(b)<32*2**20
        assert p.suffix not in ['.pt','.lmdb']
        if expected:assert sha(b)==expected
        if p.is_relative_to(R):sources[str(p.relative_to(R))]=b
        else:external.append(dict(path=str(p),sha256=sha(b),bytes=len(b),copied=False))
        return b
    def read(p):return json.loads(add(p))
    stop=read(R/'GUIDE_STOP.json');assert stop['guide_sha256']==sha(add(R/'user_repair_guide.md'))
    assert stop['reason'] in ['D3_MESSAGE_LAYER_CAPABILITY_FAILED','STAGE3_GATES_NOT_ALL_PASSED']
    packet=read(a.packet_dir/'packet_receipt.json');assert packet['model_updates']==0 and not packet['full_training_run'] and packet['combined_pdf_pages']==4
    visual=read(a.visual_review);assert visual['status']=='ACTUAL_FINAL_FOUR_PAGE_PDF_VISUALLY_REVIEWED_PASS'
    for row in visual['artifacts']:add(row['path'],row['sha256'])
    assert visual['packet_receipt_reference']['sha256']==sha(sources[str((a.packet_dir/'packet_receipt.json').relative_to(R))])
    acct=read(a.accounting);assert acct['status']=='ACTUAL_ALL_REGISTERED_REPAIR_PARENTS_TERMINAL' and acct['active_parent_ids']==[]
    assert acct['host'].split('.')[0]=='sonmi' and acct['uid']==1278
    row=acct['rows'][packet['job_id']];assert row['State']=='COMPLETED' and row['ExitCode']=='0:0'
    archive=read(a.archive_receipt);assert not archive['errors'] and archive['records'] and all(row['archival_status']=='ARCHIVED' for row in archive['records'])
    retirement=read(a.service_retirement);assert retirement['status']=='OWN_SREPAIR_METADATA_SERVICES_RETIRED_AFTER_ALL_JOBS_AND_ARCHIVES_CLOSED'
    for row in packet['artifacts']+packet['source_references']+[packet['gate_reference'],packet['parent_snapshot_reference'],packet['stop_record_reference']]:add(row['path'],row['sha256'])
    # Files created by the packet renderers are all small and listed in the immutable receipt.
    for n in ['complete/render_receipt.json','complete/D3/measurements.json','summary/summary_measurements.json']:
        d=read(a.packet_dir/n)
        for row in d.get('scientific_inputs',[])+d.get('source_references',[])+d.get('renderer_source_references',[]):add(row['path'],row['sha256'])
    summary=json.loads(sources[str((a.packet_dir/'summary/summary_measurements.json').relative_to(R))]);assert not summary['full_training_run']
    binding=read(R/'configs/D3_source_binding_v4.json')
    for row in binding['files']:add(row['path'],row['sha256'])
    for phase in packet['phases']:
        control=R/'control'/phase;jobs=read(control/'jobs.json')
        for name in ['status.json','tasks.json','LR_selection.json','identity.json','bootstrap_start.json']:
            if (control/name).is_file():add(control/name)
        for key,job in jobs.items():
            jid=job['job_id'];row=acct['rows'][jid];assert row['State']=='COMPLETED' and row['ExitCode']=='0:0'
            add(job['configuration'],job['configuration_sha256']);p=read(R/'reports'/(key+'_latest.json'));b=add(p['path'],p['sha256']);result=json.loads(b)
            assert result['optimizer_updates']==4000 and result['runtime']['job_id']==jid
            add(Path(p['path']).with_name('curve.json'))
        if phase.startswith('d3_message'):
            layer=phase[len('d3_message')];add(R/'configs'/('message'+layer+'_capability_authorization_v1.json'));add(R/'configs'/('D3_message'+layer+'_plan_v1.json'))
    for pointer in ['D1_latest.json','D2_latest.json','lookup_latest.json','preselection_performance_crossover_latest.json','performance_crossover_latest.json']:
        p=R/'reports'/pointer
        if p.is_file():row=read(p);add(row['path'],row['sha256'])
    for n in ['source_v3/docs/SOURCE_MANIFEST.json','source_v3/current/tests/test_equivariant_denoising.py',
        'reports/core_repair_patch_v1/s_denoise_core_v3.patch','reports/core_repair_patch_v1/receipt.json',
        'reports/D1_D2_completed_v2.pdf','reports/D1_D2_completed_v2_render.json','reports/D1_D2_completed_v2_visual_review_v1.json',
        'configs/gate_analysis_binding_v3.json','configs/cost_estimator_v2.json','configs/lookup_refit_closure_v1.json',
        'reports/source_v3_repository_check_v26.json','analysis/stage3_gate_v4.py','analysis/profile_completed_d3_conditions_v3.py']:
        add(R/n)
    for row in acct['rows'].values():
        for entry in row['submission_references']:
            add(entry['reference']['path'],entry['reference']['sha256']);add(entry['script_reference']['path'],entry['script_reference']['sha256'])
    # Record all actual final costs after the rendering parent closes; no recursive self-estimate.
    note='S去噪修复：所有已登记Slurm父任务均已终止；失败、取消和超时全部保留。\n'
    note+=f"唯一父任务数：{acct['unique_registered_parent_count']}\n实际分配CPU核时：{acct['allocated_CPU_core_hours']}\nGPU节点作业分配小时：{acct['GPU_node_allocation_hours']}\n"
    note+='GPU节点作业分配小时包括启动、验证和等待，不代表GPU利用率或独占时长。全量B1/B3未运行。\n'
    sources['最终实际成本说明.txt']=note.encode('utf-8')
    manifest=dict(status='FINAL_GUIDE_STOP_DIAGNOSTIC_DELIVERY_ALL_ACTUAL_PARENTS_TERMINAL',created_unix=time.time(),
        guide_sha256=stop['guide_sha256'],stop_reason=stop['reason'],full_training_run=False,scientific_gate_passed=False,
        report_entrypoint=str((a.packet_dir/'S_denoise_repair_diagnostic_report.pdf').relative_to(R)),
        summary_entrypoint=str((a.packet_dir/'summary/诊断结论.md').relative_to(R)),
        files=[dict(relative_path=n,sha256=sha(b),bytes=len(b),source_path=str(R/n)) for n,b in sorted(sources.items())],external_immutable_references=external,
        accounting_reference=dict(path=str(a.accounting),sha256=sha(sources[str(a.accounting.relative_to(R))])),
        closed_WandB_archive_receipt=dict(path=str(a.archive_receipt),sha256=sha(sources[str(a.archive_receipt.relative_to(R))])),
        all_models_and_raw_LMDB_excluded_from_small_delivery=True)
    with zipfile.ZipFile(a.output,'x',compression=zipfile.ZIP_STORED) as z:
        for n,b in sorted(sources.items()):z.writestr(n,b)
        z.writestr('delivery_manifest.json',json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    proof=dict(status=manifest['status'],archive_path=str(a.output),archive_sha256=sha(a.output.read_bytes()),archive_bytes=a.output.stat().st_size,files=len(sources),report_entrypoint=manifest['report_entrypoint'])
    with a.output.with_suffix('.zip.receipt.json').open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
    print(json.dumps(proof))
if __name__=='__main__':main()
