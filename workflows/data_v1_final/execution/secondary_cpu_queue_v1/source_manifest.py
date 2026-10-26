"""Main-side small-source review/locator manifest; no Alpha transfer or execution."""
import argparse,json,os
from pathlib import Path
from .common import ROOT,ENDPOINT,UID,PACKAGE,need,read_small,sha,canonical


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--reviewer',required=True)
    args=parser.parse_args();here=Path(__file__).absolute().parent
    need(args.reviewer=='root' and os.name=='posix' and os.getuid()==1278 and
         here==Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/execution/secondary_cpu_queue_v1'),
         'ROOT_MAIN_INTEGRATED_SOURCE_REVIEW_INVOCATION_REQUIRED')
    rows=[]
    for path in sorted(here.glob('*.py')):
        raw=read_small(path,inside=False);origin={'path':str(path),'bytes':len(raw),'sha256':sha(raw)}
        rows.append({'origin_reference':origin,'target_locator':dict(origin,path=str(PACKAGE/path.name)),
                     'target_current_bytes_verified':False})
    review={'schema':'ROOT_SECONDARY_CPU_CONTROLLER_SOURCE_REVIEW_V1','status':'APPROVED_FOR_METADATA_CONTROL_ONLY',
        'reviewer':'root','endpoint':ENDPOINT,'uid':UID,'run_root':str(ROOT),'login_hostname':'sonmi','sources':rows,
        'alpha_installation_claimed':False,'source_review_is_not_job_or_science_admission':True}
    need(args.output.is_absolute() and not args.output.exists(),'NEW_MAIN_REVIEW_OUTPUT_REQUIRED')
    raw=canonical(review)+b'\n';need(len(raw)<=2*1024**2,'SMALL_SOURCE_REVIEW_REQUIRED')
    with args.output.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    print(json.dumps({'status':review['status'],'origin_output':str(args.output),'bytes':len(raw),'sha256':sha(raw),
                      'planned_alpha_source_files':len(rows),'actual_alpha_targets_verified':False}))


if __name__=='__main__':main()
