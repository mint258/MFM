"""Wait for our postlude exit markers; no scheduler or scientific input reads."""
import argparse, json, time
from pathlib import Path

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--seconds',type=float,default=3600)
    parser.add_argument('--cost-job',required=True)
    parser.add_argument('--report-job',required=True)
    args=parser.parse_args()
    deadline=time.monotonic()+args.seconds
    markers=[('report', ROOT/'logs'/f'wp4_final_report_v4_{args.report_job}.exitcode'),
             ('cost', ROOT/'logs'/f'wp4_polar_cost_v2_{args.cost_job}.exitcode')]
    reason='hourly_check_due'
    while time.monotonic()<deadline:
        for stage,path in markers:
            if path.exists():
                status=path.read_text().strip()
                if stage=='report' or status!='0':
                    reason=f'{stage}_exit_{status}'
                    print('WAIT_STAGE_DONE '+json.dumps({'reason':reason,'marker':str(path)}),flush=True)
                    return
        time.sleep(min(20,max(0,deadline-time.monotonic())))
    print('WAIT_STAGE_DONE '+json.dumps({'reason':reason}),flush=True)

if __name__=='__main__':
    main()
