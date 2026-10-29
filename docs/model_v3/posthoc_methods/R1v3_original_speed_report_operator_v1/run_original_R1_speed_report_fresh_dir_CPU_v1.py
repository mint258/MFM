"""CPU-only operator: create fresh output after original supervisor admission."""
import argparse,pathlib,runpy,sys
p=argparse.ArgumentParser();p.add_argument('--old',choices=['4520405','4520486','4520411','4520456','4520549','4520438'],required=True);a=p.parse_args()
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
out=N/('R1v3_old'+a.old+'_speed_report_actual_v3');assert not out.exists();out.mkdir()
f=N/'performance_remaining_Av2_R1_ABBA_v3'/('cohort_'+a.old)
tool=B/'MFM_model_v3_A_acceptance_v2_candidate_v1/tools/model_v3/a_speed_report.py'
sys.path.insert(0,str(tool.parent))
sys.argv=[str(tool),'--runs',*[str(f/('member_'+str(i))/'child') for i in range(1,5)],'--supervisors',*[str(f/('member_'+str(i))/'supervisor.json') for i in range(1,5)],'--numeric-gate',str(N/'performance_remaining_Av2_20261029_routing_v7/trials'/('recheck_'+a.old+'_routing_v7')/'child'),'--output',str(out/'report.json')]
runpy.run_path(str(tool),run_name='__main__')
