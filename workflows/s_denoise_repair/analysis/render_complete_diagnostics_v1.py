"""CPU rendering of closed D3 measurements/gate plus actual-PDF rasters; no model updates."""
import argparse,hashlib,json,os,shutil,socket,subprocess,sys,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
def ref(path):
    p=Path(path);b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phases',nargs='+',required=True);ap.add_argument('--parent-snapshot',type=Path,required=True)
    ap.add_argument('--gate',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--performance-reference',type=Path);a=ap.parse_args()
    assert os.getuid()==1278 and os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    assert socket.gethostname().split('.')[0] in ['compute-0-'+str(n) for n in [2,8,9,10,11,12,13,14,15,16,17,18,19]]
    assert a.output_dir.is_absolute() and a.output_dir.is_relative_to(R/'reports') and not a.output_dir.exists()
    assert a.parent_snapshot.is_absolute() and a.parent_snapshot.is_relative_to(R/'control/accounting_snapshots')
    assert a.gate.is_absolute() and a.gate.is_relative_to(R/'reports')
    rasterizer=shutil.which('pdftoppm');assert rasterizer,'ACTUAL_PDF_RASTERIZER_NOT_AVAILABLE'
    a.output_dir.mkdir(parents=True);commands=[];start=time.monotonic()
    env=dict(os.environ);cache=R/'cache'/('mpl_job'+os.environ['SLURM_JOB_ID']);cache.mkdir(parents=True,exist_ok=False);env['MPLCONFIGDIR']=str(cache)
    def run(name,argv):
        executed=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180,env=env)
        (a.output_dir/(name+'.stdout.txt')).write_text(executed.stdout);(a.output_dir/(name+'.stderr.txt')).write_text(executed.stderr)
        commands.append(dict(name=name,argv=argv,returncode=executed.returncode));assert executed.returncode==0,(name,executed.stderr[-1200:])
    run('D3_curves',[sys.executable,'-B',str(R/'analysis/render_d3_report_v4.py'),'--phases']+a.phases+[
        '--parent-snapshot',str(a.parent_snapshot),'--output-dir',str(a.output_dir/'D3'),'--gate',str(a.gate),'--require-complete'])
    gate_args=[sys.executable,'-B',str(R/'analysis/render_stage3_gate_v2.py'),'--gate',str(a.gate),'--output-dir',str(a.output_dir/'gate')]
    if a.performance_reference:gate_args+=['--performance-reference',str(a.performance_reference)]
    run('Stage3_gate',gate_args)
    for name,pdf in [('D3',a.output_dir/'D3/D3_curves.pdf'),('gate',a.output_dir/'gate/Stage3_gate.pdf')]:
        reference=ref(pdf);prefix=pdf.with_name(pdf.stem+'_actual_pdf')
        run(name+'_actual_PDF_raster',[rasterizer,'-f','1','-singlefile','-scale-to','2000','-png',str(pdf),str(prefix)])
        assert ref(pdf)==reference and prefix.with_suffix('.png').is_file()
    files=sorted(p for p in a.output_dir.rglob('*') if p.is_file());assert all(not p.is_symlink() for p in files)
    document=dict(status='COMPLETE_D3_AND_STAGE3_PAGE_RENDERED_ACTUAL_PDFS_AWAIT_VISUAL_REVIEW',job_id=os.environ['SLURM_JOB_ID'],
        phases=a.phases,gate_reference=ref(a.gate),parent_snapshot_reference=ref(a.parent_snapshot),
        renderer_source_references=[ref(R/'analysis'/name) for name in ['render_d3_report_v4.py','render_stage3_gate_v2.py','render_complete_diagnostics_v1.py']],
        commands=commands,artifacts=[ref(p) for p in files],elapsed_seconds=time.monotonic()-start,
        model_updates=0,full_training_complete_claimed=False,visual_review_still_required=True)
    with (a.output_dir/'render_receipt.json').open('x') as f:json.dump(document,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(status=document['status'],job_id=document['job_id'],output=str(a.output_dir))))
if __name__=='__main__':main()
