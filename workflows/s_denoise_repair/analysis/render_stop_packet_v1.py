"""Actual CPU STOP packet: all curves, gate, causal summary and four-page PDF."""
import argparse,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
def ref(p):
    p=Path(p);b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phases',nargs='+',required=True);ap.add_argument('--profiles',type=Path,nargs='+',required=True)
    ap.add_argument('--parent-snapshot',type=Path,required=True);ap.add_argument('--gate',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--performance-reference',type=Path);a=ap.parse_args()
    assert os.getuid()==1278 and os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert a.output_dir.is_absolute() and a.output_dir.is_relative_to(R/'reports') and not a.output_dir.exists()
    assert (R/'GUIDE_STOP.json').is_file()
    for name in ['pdfunite','pdftoppm','pdfinfo']:assert shutil.which(name),name
    a.output_dir.mkdir(parents=True);env=dict(os.environ);cache=R/'cache'/('mpl_stop_job'+os.environ['SLURM_JOB_ID']);cache.mkdir(exist_ok=False);env['MPLCONFIGDIR']=str(cache);env['LC_ALL']='C'
    commands=[];started=time.monotonic()
    def run(name,argv):
        p=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,env=env,timeout=240)
        (a.output_dir/(name+'.stdout.txt')).write_text(p.stdout);(a.output_dir/(name+'.stderr.txt')).write_text(p.stderr)
        commands.append(dict(name=name,argv=argv,returncode=p.returncode));assert p.returncode==0,(name,p.stderr[-1500:]);return p.stdout
    argv=[sys.executable,'-B',str(R/'analysis/render_complete_diagnostics_v1.py'),'--phases']+a.phases+['--parent-snapshot',str(a.parent_snapshot),'--gate',str(a.gate),'--output-dir',str(a.output_dir/'complete')]
    if a.performance_reference:argv+=['--performance-reference',str(a.performance_reference)]
    run('complete_D3_gate',argv)
    run('STOP_summary',[sys.executable,'-B',str(R/'analysis/build_stop_diagnostic_summary_v1.py'),'--phases']+a.phases+['--profiles']+[str(p) for p in a.profiles]+['--parent-snapshot',str(a.parent_snapshot),'--gate',str(a.gate),'--output-dir',str(a.output_dir/'summary')])
    pdfs=[a.output_dir/'summary/Diagnostic_stop_summary.pdf',R/'reports/D1_D2_completed_v2.pdf',a.output_dir/'complete/D3/D3_curves.pdf',a.output_dir/'complete/gate/Stage3_gate.pdf']
    combined=a.output_dir/'S_denoise_repair_diagnostic_report.pdf';run('merge_actual_PDFs',['pdfunite']+[str(p) for p in pdfs]+[str(combined)])
    info=run('combined_PDF_metadata',['pdfinfo',str(combined)]);pages=int(next(line.split(':',1)[1].strip() for line in info.splitlines() if line.startswith('Pages:')));assert pages==4
    initial_ref=ref(combined)
    run('combined_actual_PDF_rasters',['pdftoppm','-f','1','-l','4','-scale-to','2000','-png',str(combined),str(a.output_dir/'report_actual_page')])
    assert ref(combined)==initial_ref;rasters=sorted(a.output_dir.glob('report_actual_page-*.png'));assert len(rasters)==4
    artifacts=[ref(p) for p in sorted(a.output_dir.rglob('*')) if p.is_file()];assert all(not Path(row['path']).is_symlink() for row in artifacts)
    doc=dict(status='COMPLETE_GUIDE_STOP_PACKET_AWAITING_ACTUAL_FOUR_PAGE_VISUAL_REVIEW',job_id=os.environ['SLURM_JOB_ID'],phases=a.phases,
      source_references=[ref(R/'analysis'/name) for name in ['render_stop_packet_v1.py','render_complete_diagnostics_v1.py','render_d3_report_v4.py','render_stage3_gate_v2.py','build_stop_diagnostic_summary_v1.py']],
      stop_record_reference=ref(R/'GUIDE_STOP.json'),gate_reference=ref(a.gate),parent_snapshot_reference=ref(a.parent_snapshot),
      combined_pdf_reference=initial_ref,combined_pdf_pages=pages,raster_references=[ref(p) for p in rasters],artifacts=artifacts,commands=commands,
      elapsed_seconds=time.monotonic()-started,model_updates=0,full_training_run=False,
      final_actual_accounting_appendix_required_after_this_parent_closes=True,visual_review_still_required=True)
    with (a.output_dir/'packet_receipt.json').open('x') as f:json.dump(doc,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(status=doc['status'],job_id=doc['job_id'],output=str(a.output_dir))))
if __name__=='__main__':main()
