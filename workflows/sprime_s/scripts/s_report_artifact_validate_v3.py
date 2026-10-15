"""Validate delivered report evidence and render its five-item first page."""
import csv,json,os,re,subprocess,time
from prepare import ROOT,save,sha

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    output=ROOT/'reports/current_experiment'
    summary=json.loads((output/'summary.json').read_text())
    assert summary['job_id']==os.environ['SLURM_JOB_ID']
    assert summary['report_source_sha256']==sha(ROOT/'scripts/report_s_experiment_current_v6.py')
    assert summary['A_accepted']
    accepted=json.loads((ROOT/'dataset/acceptance.json').read_text())
    assert accepted['status']=='FULL_DATASET_ACCEPTED'
    assert summary['A']['molecules']==1220466 and summary['A']['source_S_conformers']==11231854
    subprocess.run(['pdftotext','-f','1','-l','1',str(output/'report.pdf'),str(output/'first_page.txt')],check=True,timeout=60)
    text=(output/'first_page.txt').read_text()
    expected=['One epoch sufficient:','Denoiser vs lookup0.042 A:','Single-epoch wall time:','S-prime generation:','User decisions:']
    assert all(text.count(item)==1 for item in expected)
    assert len(re.findall(r'(?m)^[1-5]\. ',text))==5
    subprocess.run(['pdftoppm','-f','1','-singlefile','-scale-to','1500','-png',str(output/'report.pdf'),str(output/'first_page')],check=True,timeout=60)
    required=['summary.json','report.pdf','training_curves.png','training_curves.svg','validation_curves.png','validation_curves.svg','runtime_curves.png','runtime_curves.svg','first_page.txt','first_page.png']
    final=summary['status']=='FULL_COMPUTATIONS_AND_REPORT_GENERATED_AWAITING_REVIEW'
    if final:
        assert summary['B_status']=='ALL_THREE_TRAINING_RUNS_COMPLETE_AWAITING_H0_PROBES'
        assert summary['all_required_probes_closed'] and len(summary['probe_comparisons'])==35
        assert sum(row['included_in_primary_judgment'] for row in summary['probe_comparisons'])==32
        assert summary['downstream_policy']['cells_per_checkpoint']==41
        assert len(summary['loss_comparisons'])==3
        for name,value in summary['conditions'].items():
            epochs=3 if name=='B3_seed0' else 1
            assert value['actual_terminal_records']==11104772*epochs
            assert len(value['complete_epochs'])==epochs
            assert all(row['records']==11104772 and row['molecules']==1206608 and row['missing']==0 and row['duplicates']==0 for row in value['complete_epochs'])
            assert len(summary['epoch_wall_timing'][name])==epochs
        assert len(summary['epoch1_denoising_lookup_checks'])==3
        points=['B1_seed0_e1','B1_seed1_e1','B3_seed0_e0p25','B3_seed0_e0p5','B3_seed0_e1','B3_seed0_e2','B3_seed0_e3']
        for point in points:
            receipt=json.loads((ROOT/'probe_results_v2'/point/'receipt.json').read_text())
            assert receipt['status']=='ALL_FORTY_ONE_FROZEN_LINEAR_PROBE_CELLS_CLOSED'
            assert len(receipt['cells'])==41 and len(receipt['aggregate'])==35
            assert not receipt['expansion_official_test_rows_used_for_training']
            expansion=[row for row in receipt['cells'] if row['dataset']=='expansionrx']
            assert len(expansion)==1
            assert expansion[0]['train_inventory_records']==5326 and expansion[0]['test_inventory_records']==2282
            assert expansion[0]['validation_geometry_ready_records']==0
            assert all(not row['encoder_trained'] and not row['test_targets_used_for_model_or_endpoint_selection'] for row in receipt['cells'])
            features=json.loads((ROOT/'probe_h0_v1'/point/'receipt.json').read_text())
            assert features['encoder_parameters_and_buffers_unchanged']
        rows=list(csv.DictReader((output/'all_checkpoint_probe_metrics.csv').open(newline='')))
        assert len(rows)==245 and len({(r['checkpoint'],r['dataset'],r['task']) for r in rows})==245
        required+=['all_checkpoint_probe_metrics.csv','checkpoint_probe_comparison.csv','validation_metrics.csv']
    artifacts=[]
    for name in required:
        path=output/name;assert path.stat().st_size>0
        artifacts.append({'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path)})
    receipt={'status':'FINAL_ARTIFACT_CLOSURE_PASS_AWAITING_VISUAL_REVIEW' if final else 'CURRENT_PROGRESS_REPORT_ARTIFACTS_PASS',
        'timestamp':time.time(),'job_id':os.environ['SLURM_JOB_ID'],'complete_experiment':final,
        'validator_source_sha256':sha(__file__),'summary_sha256':sha(output/'summary.json'),
        'first_page_exactly_five_required_items':True,'artifacts':artifacts}
    save(output/'artifact_validation.json',receipt)
    print(json.dumps({'status':receipt['status'],'complete_experiment':final}),flush=True)

if __name__=='__main__':main()
