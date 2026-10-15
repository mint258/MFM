"""Render actual immutable final PDF pages for visual acceptance."""
import concurrent.futures,json,os,subprocess,time
from prepare import ROOT,save,sha
assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
report=ROOT/'reports/current_experiment/report.pdf';summary=ROOT/'reports/current_experiment/summary.json'
accepted=json.loads((ROOT/'reports/current_experiment/artifact_validation.json').read_text())
assert accepted['job_id']=='4515415' and accepted['status']=='FINAL_ARTIFACT_CLOSURE_PASS_AWAITING_VISUAL_REVIEW'
before=sha(report);output=ROOT/'reports/final_visual_review_v1';output.mkdir(exist_ok=False)
def render(page):
    prefix=output/('page_'+str(page));subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-singlefile','-scale-to','1800','-png',str(report),str(prefix)],check=True,timeout=60)
    path=prefix.with_suffix('.png');assert path.stat().st_size>0
    return {'page':page,'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path)}
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:pages=list(pool.map(render,range(2,8)))
assert sha(report)==before
save(output/'render_receipt.json',{'status':'ACTUAL_FINAL_PDF_PAGES_RENDERED_AWAITING_VISUAL_REVIEW','render_job_id':os.environ['SLURM_JOB_ID'],'report_job_id':'4515415','pdf_sha256':before,'summary_sha256':sha(summary),'first_page_path':str(ROOT/'reports/current_experiment/first_page.png'),'first_page_sha256':sha(ROOT/'reports/current_experiment/first_page.png'),'pages':pages,'source_sha256':sha(__file__),'timestamp':time.time()})
print('ACTUAL_FINAL_PDF_PAGES_RENDERED_AWAITING_VISUAL_REVIEW')
