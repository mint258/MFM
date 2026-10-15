"""Finalize only physically complete experiments with actual final visual review."""
import argparse,csv,json,os,socket,subprocess,time
from pathlib import Path
from prepare import ROOT,save,sha

def read(path):return json.loads(Path(path).read_text())
def ref(path):
    path=Path(path);return {'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path)}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--visual-review-json',required=True);args=parser.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    destination=ROOT/'reports/final_experiment_acceptance.json';assert not destination.exists()
    b=read(ROOT/'formal_s/root_coordinator_v1_status.json');p=read(ROOT/'probe_preparation_control/finish_root_v2_status.json');r=read(ROOT/'report_control/status_v6.json')
    assert b['status']=='ALL_THREE_TRAINING_RUNS_COMPLETE_AWAITING_H0_PROBES'
    assert p['status']=='ALL_SEVEN_ENDPOINTS_AND_OVERLAP_CLOSED'
    assert r['status']=='FINAL_REPORT_AND_ARTIFACT_CLOSURE_COMPLETE_AWAITING_VISUAL_REVIEW'
    assert not (ROOT/'formal_s/scientific_stop.json').exists()
    summary_path=ROOT/'reports/current_experiment/summary.json';summary=read(summary_path)
    artifacts_path=ROOT/'reports/current_experiment/artifact_validation.json';artifacts=read(artifacts_path)
    assert summary['status']=='FULL_COMPUTATIONS_AND_REPORT_GENERATED_AWAITING_REVIEW'
    assert artifacts['status']=='FINAL_ARTIFACT_CLOSURE_PASS_AWAITING_VISUAL_REVIEW' and artifacts['complete_experiment']
    report_job=summary['job_id'];assert report_job==artifacts['job_id']==r['report_job']['job_id']
    assert artifacts['summary_sha256']==sha(summary_path)
    for item in artifacts['artifacts']:
        assert Path(item['path']).stat().st_size==item['bytes'] and sha(item['path'])==item['sha256']
    visual=read(args.visual_review_json)
    assert visual['status']=='FINAL_PDF_VISUAL_REVIEW_PASS' and visual['report_job_id']==report_job
    assert visual['summary_sha256']==sha(summary_path)
    assert visual['pdf_sha256']==sha(ROOT/'reports/current_experiment/report.pdf')
    assert visual['rendered_first_page_sha256']==sha(ROOT/'reports/current_experiment/first_page.png')
    assert visual['first_page_exactly_five_required_items'] and visual['readable_without_clipping_or_overlap']
    assert set(visual['checked_pages'])>={1,2,3,4,5,6,7}
    for binding_path in [ROOT/'formal_s/controller_binding_v3.json',ROOT/'report_control/binding_v6.json']:
        binding=read(binding_path)
        for item in binding['sources']+binding.get('configurations',[]):assert sha(item['path'])==item['sha256']
    accepted=read(ROOT/'dataset/acceptance.json');assert accepted['status']=='FULL_DATASET_ACCEPTED'
    assert summary['A_accepted'] and summary['A']['molecules']==1220466 and summary['A']['source_S_conformers']==11231854 and summary['A']['sprime_conformers']==10782661
    assert len(summary['loss_comparisons'])==3 and len(summary['probe_comparisons'])==35
    assert sum(bool(row['included_in_primary_judgment']) for row in summary['probe_comparisons'])==32
    assert summary['one_epoch_judgment'] in ['ONE_EPOCH_INSUFFICIENT_UNDER_PREDECLARED_RULE','ONE_EPOCH_SUFFICIENT_UNDER_PREDECLARED_RULE','NOT_ESTABLISHED_DUE_TO_UNAVAILABLE_PROBE_CELLS']
    formal_jobs=[]
    for path in (ROOT/'submission').glob('formal_s_*_attempt*.json'):
        entry=read(path)
        if entry.get('job_id'):formal_jobs.append(entry['job_id'])
    formal_jobs=sorted(set(formal_jobs))
    latest_jobs=[]
    for condition,value in summary['conditions'].items():
        epochs=3 if condition=='B3_seed0' else 1
        assert value['actual_terminal_records']==11104772*epochs and len(value['complete_epochs'])==epochs
        assert all(row['records']==11104772 and row['molecules']==1206608 and row['missing']==0 and row['duplicates']==0 for row in value['complete_epochs'])
        assert len(summary['epoch_wall_timing'][condition])==epochs
        latest_jobs.append(b['conditions'][condition]['latest_job_id'])
    points=['B1_seed0_e1','B1_seed1_e1','B3_seed0_e0p25','B3_seed0_e0p5','B3_seed0_e1','B3_seed0_e2','B3_seed0_e3']
    probe_refs=[];probe_jobs=[]
    for point in points:
        hp=ROOT/'probe_h0_v1'/point/'receipt.json';lp=ROOT/'probe_results_v2'/point/'receipt.json';h=read(hp);l=read(lp)
        assert h['status']=='ALL_FIVE_FROZEN_H0_DATASETS_CLOSED' and not h['development_only'] and h['encoder_parameters_and_buffers_unchanged']
        assert l['status']=='ALL_FORTY_ONE_FROZEN_LINEAR_PROBE_CELLS_CLOSED' and len(l['cells'])==41 and len(l['aggregate'])==35 and l['primary_tasks']==32
        assert not l['expansion_official_test_rows_used_for_training']
        assert l['encoder_checkpoint']==h['checkpoint_reference']
        probe_jobs += [h['job_id'],l['job_id']];probe_refs.append({'endpoint':point,'H0':ref(hp),'linear_probes':ref(lp),'checkpoint_reference':l['encoder_checkpoint']})
    csv_path=ROOT/'reports/current_experiment/all_checkpoint_probe_metrics.csv';rows=list(csv.DictReader(csv_path.open(newline='')))
    assert len(rows)==245 and len({(row['checkpoint'],row['dataset'],row['task']) for row in rows})==245
    jobs=sorted(set(formal_jobs+probe_jobs+[report_job]));q=subprocess.run(['sacct','-j',','.join(jobs),'-n','-P','--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],capture_output=True,text=True,check=True,timeout=60)
    parents={cols[0]:cols for line in q.stdout.splitlines() if (cols:=line.split('|'))[0] in jobs}
    assert set(parents)==set(jobs) and all(v[1]=='zixiao' for v in parents.values())
    assert all(parents[j][2:4]==['COMPLETED','0:0'] for j in latest_jobs+probe_jobs+[report_job])
    assert all(v[2] in ['COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'] for v in parents.values())
    outcome={'status':'FULL_EXPERIMENT_ACCEPTED','timestamp':time.time(),'guide':ref(ROOT/'configs/user_guide.md'),
        'A_acceptance':ref(ROOT/'dataset/acceptance.json'),'A_manifest':ref(ROOT/'dataset/manifest.json'),'A_sha_manifest':ref(ROOT/'dataset/sha_manifest.json'),
        'summary':ref(summary_path),'report_artifact_validation':ref(artifacts_path),'report_pdf':ref(ROOT/'reports/current_experiment/report.pdf'),
        'visual_review':ref(args.visual_review_json),'one_epoch_judgment':summary['one_epoch_judgment'],
        'training_epochs_completed':{'B1_seed0':1,'B1_seed1':1,'B3_seed0':3},'training_records_per_epoch':11104772,'folded_molecules_per_epoch':1206608,
        'formal_probe_endpoints':7,'linear_probe_cells':287,'checkpoint_task_rows':245,'reported_tasks_per_endpoint':35,'primary_tasks_per_endpoint':32,
        'loss_comparisons':summary['loss_comparisons'],'epoch1_denoising_lookup_checks':summary['epoch1_denoising_lookup_checks'],
        'marginal_epoch_estimate':summary['marginal_epoch_estimate'],'actual_sacct_parents':parents,'actual_sacct_raw_stdout':q.stdout,
        'formal_S_allocated_core_hours_including_failed_attempts':sum(int(parents[j][4])*int(parents[j][5])/3600 for j in formal_jobs),
        'historical_failed_attempts_retained':[j for j in formal_jobs if parents[j][2]!='COMPLETED'],'probe_receipts_and_checkpoint_references':probe_refs,
        'source_bindings':[ref(ROOT/'formal_s/controller_binding_v3.json'),ref(ROOT/'report_control/binding_v6.json')],
        'frozen_reference_user_confirmation':ref(ROOT/'formal_s/user_frozen_reference_confirmation_20261014_v2.json'),
        'scientific_stop_triggered':False,'further_training_experiments_in_this_acceptance':False,'paid_school_server_used':False}
    save(destination,outcome)
    print('FULL_EXPERIMENT_ACCEPTED',summary['one_epoch_judgment'])

if __name__=='__main__':main()
