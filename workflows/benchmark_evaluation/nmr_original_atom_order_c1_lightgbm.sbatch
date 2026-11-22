sbatch --parsable --dependency=afterok:4537149:4537317 <<'C1NMRPPRIME'
#!/bin/bash
#SBATCH --job-name=C1-NMR-atomic-Pprime-LightGBM
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_NMR_Pprime_LGBM_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import csv,json,math,os,time,traceback,unittest
from collections import Counter
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from lightgbm import LGBMRegressor
from workflows.benchmark_data.admission import protect
SEED=20261025
def score(y,prediction,train_mean,groups,draws=1000):
    y=np.asarray(y,float);prediction=np.asarray(prediction,float);groups=np.asarray(groups)
    if y.ndim!=1 or y.shape!=prediction.shape or y.shape!=groups.shape or not len(y):raise ValueError('Unaligned evaluation rows')
    if not np.isfinite(y).all() or not np.isfinite(prediction).all() or not math.isfinite(train_mean):raise ValueError('Nonfinite labels or predictions')
    unique,inverse=np.unique(groups,return_inverse=True)
    error=np.abs(y-prediction);reference=np.abs(y-train_mean)
    numerator=np.bincount(inverse,weights=error,minlength=len(unique))
    denominator=np.bincount(inverse,weights=reference,minlength=len(unique))
    total=float(denominator.sum())
    result={'MAE':float(error.mean()),'RAE':None,'RAE_CI95_low':None,'RAE_CI95_high':None,'n_test_rows':len(y),'n_test_molecules':len(unique),'bootstrap_draws':draws,'undefined_bootstrap_draws':0}
    if total<=0:return dict(result,metric_status='ZERO_TRAIN_MEAN_REFERENCE_ERROR')
    result['RAE']=float(numerator.sum()/total)
    rng=np.random.default_rng(SEED);values=[]
    for _ in range(draws):
        sample=rng.integers(0,len(unique),size=len(unique));divisor=float(denominator[sample].sum())
        if divisor<=0:result['undefined_bootstrap_draws']+=1
        else:values.append(float(numerator[sample].sum()/divisor))
    if result['undefined_bootstrap_draws']:return dict(result,metric_status='UNDEFINED_BOOTSTRAP_REFERENCE_DRAWS')
    result['RAE_CI95_low'],result['RAE_CI95_high']=map(float,np.quantile(values,[.025,.975]))
    return dict(result,metric_status='OK')

def atomic_points(rows):
    points=[]
    for row in rows:
        for atom in row['atoms']:
            p=atom['Pprime_features'];mask=atom['Pprime_valid_mask'];rdkit=atom['rdkit_atom37']
            if len(rdkit)!=37:raise ValueError('Original RDKit atom37 layout changed')
            if p is not None and (mask is None or len(mask)!=len(p)):raise ValueError('Native atomic Pprime mask differs from its fields')
            available=p is not None and any(mask)
            features=list(p)+list(rdkit) if available else None
            points.append(dict(record_id=row['record_id']+':atom:'+str(atom['original_atom_index']),
                original_spectrum_record_id=row['record_id'],original_atom_index=atom['original_atom_index'],
                full_inchikey=row['full_inchikey'],official_split=row['official_split'],y=atom['y'],
                retained=row['retained'],domain_eligible=row['domain_eligible'],features=features))
    return points
class AtomicPprimeReadoutTests(unittest.TestCase):
    def row(self,p,mask):
        return dict(record_id='NMR2018:1H:test:row:2',full_inchikey='FULL-KEY',official_split='test',
                    retained=True,domain_eligible=True,atoms=[dict(original_atom_index=7,y=2.3,
                    Pprime_features=p,Pprime_valid_mask=mask,rdkit_atom37=list(range(37)))])
    def test_missing_Pprime_does_not_become_a_RDKit_only_C1_prediction(self):
        self.assertIsNone(atomic_points([self.row(None,None)])[0]['features'])
    def test_original_atomic_identity_and_native_missing_fields_are_preserved(self):
        actual=atomic_points([self.row([1.,float('nan')],[True,False])])[0]
        self.assertEqual(actual['record_id'],'NMR2018:1H:test:row:2:atom:7')
        self.assertTrue(math.isnan(actual['features'][1]))
        self.assertEqual(len(actual['features']),39)
        self.assertEqual(actual['official_split'],'test')
    def test_partial_Pprime_masks_are_required(self):
        with self.assertRaises(ValueError):atomic_points([self.row([1.,2.],[True])])

suite=unittest.defaultTestLoader.loadTestsFromTestCase(AtomicPprimeReadoutTests)
if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,2147483648,quota,own_concurrent_bytes=40*1024**3)
features=b1/'C1_Pprime_reference_features/job_4537149';source=json.loads((features/'manifest.json').read_text())
if source['status']!='C1_PPRIME_REFERENCE_OPTICAL_AND_ATOMIC_FEATURES_CLOSED':raise ValueError('Native atomic feature source is not closed')
safe();out=b1/'C1_NMR_Pprime_LGBM'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True)
tmp=out/'tmp';tmp.mkdir();os.environ['TMPDIR']=str(tmp);os.environ['TEMP']=str(tmp);os.environ['TMP']=str(tmp)
prediction_schema=pa.schema([('dataset',pa.string()),('task',pa.string()),('model',pa.string()),('feature_group',pa.string()),('record_id',pa.string()),('original_spectrum_record_id',pa.string()),('original_atom_index',pa.int32()),('full_inchikey',pa.string()),('y_true',pa.float64()),('prediction',pa.float64()),('training_mean',pa.float64()),('retained',pa.bool_()),('domain_eligible',pa.bool_()),('prediction_origin',pa.string())])
results=[];failures=[];coverage=[]
def eligible(row):return bool(row['retained'] and row['domain_eligible'])
def rebind_original_nmr_atoms(native_P_rows, corrected_original_rows):
    """Preserve native P values, using each original graph's own atom-indexed RDKit fields."""
    corrected={r['record_id']:r for r in corrected_original_rows}
    if len(corrected)!=len(corrected_original_rows):raise ValueError('Duplicate original NMR spectrum ID')
    output=[]
    for prior in native_P_rows:
        source=corrected.get(prior['record_id'])
        if source is None:raise ValueError('Native P binding has no corrected original spectrum')
        identity=('full_inchikey','official_split','retained','domain_eligible')
        if any(prior[k]!=source[k] for k in identity):raise ValueError('Original NMR identity, split or mask changed')
        old={a['original_atom_index']:a for a in prior['atoms']}
        if len(old)!=len(prior['atoms']) or set(old)!={a['original_atom_index'] for a in source['atoms']}:
            raise ValueError('Original NMR atom label set changed')
        atoms=[]
        for atom in source['atoms']:
            previous=old[atom['original_atom_index']]
            if atom['y']!=previous['y']:raise ValueError('Original experimental NMR target changed')
            atoms.append(dict(atom,Pprime_features=previous['Pprime_features'],
                              Pprime_valid_mask=previous['Pprime_valid_mask']))
        output.append(dict(source,atoms=atoms,native_Pprime_state=prior['native_Pprime_state'],
                           native_UFF_conformer_id=prior['native_UFF_conformer_id']))
    if len(output)!=len(corrected):raise ValueError('An original NMR spectrum disappeared from native P binding')
    return output

for nucleus in ('13C','1H'):
    safe();native_P_rows=pq.read_table(features/('NMRShiftDB2_'+nucleus+'.parquet')).to_pylist()
    corrected_rows=pq.read_table(b1/'B1_NMR_features_native_order/job_4537317'/(nucleus+'.parquet')).to_pylist()
    points=atomic_points(rebind_original_nmr_atoms(native_P_rows,corrected_rows))
    del native_P_rows,corrected_rows
    train=[r for r in points if r['official_split']=='train' and eligible(r) and r['features'] is not None]
    original_test=[r for r in points if r['official_split']=='test'];test=[r for r in original_test if eligible(r) and r['features'] is not None]
    counts=dict(dataset='NMRShiftDB2',task=nucleus,original_TRAIN_points=sum(r['official_split']=='train' for r in points),original_TEST_points=len(original_test),C1_TRAIN_native_feature_points=len(train),C1_TEST_native_feature_points=len(test),C1_TEST_missing_native_Pprime_points=sum(eligible(r) and r['features'] is None for r in original_test),TEST_outside_domain_points=sum(not eligible(r) for r in original_test))
    coverage.append(counts)
    if not train or not test:
        failures.append(dict(dataset='NMRShiftDB2',task=nucleus,status='NATIVE_PPRIME_FEATURES_UNAVAILABLE_NO_IMPUTATION',coverage=counts))
        continue
    mean=float(np.mean([r['y'] for r in train]));closed=False
    for attempt in (1,2):
        safe();directory=out/(nucleus+'_attempt_'+str(attempt));directory.mkdir()
        started=time.monotonic()
        try:
            model=LGBMRegressor(random_state=SEED,n_jobs=2,verbosity=-1)
            model.fit(np.asarray([r['features'] for r in train],float),np.asarray([r['y'] for r in train],float))
            prediction=np.asarray(model.predict(np.asarray([r['features'] for r in test],float)),float)
            if len(prediction)!=len(test) or not np.isfinite(prediction).all():raise ValueError('Atomic C1 predictions are incomplete')
            metric=score([r['y'] for r in test],prediction,mean,[r['full_inchikey'] for r in test])
            record=dict(dataset='NMRShiftDB2',task=nucleus,model='LightGBM',feature_group='Pprime_plus_RDKit_atom',seed=SEED,n_train=len(train),training_mean=mean,feature_count=len(train[0]['features']),native_P_field_count=len(source['atom_P_fields']),RDKit_atom_field_count=37,evaluation_population='AVAILABLE_NATIVE_PPRIME_RETAINED_TEST',original_author_split=True,experimental_atomic_labels_not_averaged=True,missing_native_Pprime_points=counts['C1_TEST_missing_native_Pprime_points'],elapsed_seconds=time.monotonic()-started,**metric)
            lookup={r['record_id']:float(p) for r,p in zip(test,prediction)};records=[]
            for row in original_test:
                value=lookup.get(row['record_id'])
                origin='NATIVE_PPRIME_PLUS_RDKIT_ATOM' if value is not None else 'OUTSIDE_C1_DOMAIN' if not eligible(row) else 'NATIVE_PPRIME_FEATURES_MISSING'
                records.append(dict(dataset='NMRShiftDB2',task=nucleus,model='LightGBM',feature_group='Pprime_plus_RDKit_atom',record_id=row['record_id'],original_spectrum_record_id=row['original_spectrum_record_id'],original_atom_index=row['original_atom_index'],full_inchikey=row['full_inchikey'],y_true=row['y'],prediction=value,training_mean=mean,retained=row['retained'],domain_eligible=row['domain_eligible'],prediction_origin=origin))
            safe();pq.write_table(pa.Table.from_pylist(records,schema=prediction_schema),directory/'predictions.parquet',compression='zstd')
            model.booster_.save_model(str(directory/'model.txt'));(directory/'results.json').write_text(json.dumps(record,indent=2)+'\n')
            results.append(record);closed=True;print('C1_NMR_NATIVE_ATOMIC_PPRIME_MODEL_CLOSED',nucleus,len(train),len(test),'attempt',attempt,flush=True)
            break
        except Exception as error:
            failure=dict(dataset='NMRShiftDB2',task=nucleus,model='LightGBM',attempt=attempt,error=repr(error),status='FAILED_PRESERVED_FOR_SOURCE_RECOVERY' if attempt==1 else 'UNRESOLVED_TWO_CONSECUTIVE_FIT_FAILURES')
            failures.append(failure);traceback.print_exc();safe();(directory/'failure.json').write_text(json.dumps(failure,indent=2)+'\n')
    del points,train,test,original_test
fields=list(dict.fromkeys(key for row in results for key in row))
with (out/'C1_NMR_Pprime_partial_results.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=fields or ['task']);writer.writeheader();writer.writerows(results)
report=dict(status='C1_NMR_ORIGINAL_ATOMIC_PPRIME_LIGHTGBM_CLOSED',job=os.environ['SLURM_JOB_ID'],corrected_original_atom_feature_job=4537317,supersedes_unstarted_job=4537194,source_contract=str(features/'manifest.json'),tasks_expected=2,tasks_completed=len(results),coverage=coverage,failures=failures,new_interface_unit_tests=suite.countTestCases(),feature_group='Pprime_plus_RDKit_atom',native_P_units_and_original_atom_map_preserved=True,model_default_parameters=LGBMRegressor(random_state=SEED,n_jobs=2,verbosity=-1).get_params(),atomic_TabPFN_run=False,invented_atomic_D_run=False,experimental_labels_or_original_split_changed=False,missing_features_not_imputed=True,selection_used_TEST=False,hyperparameter_search=False,seed_count=1,statistics='1000 full-molecule grouped bootstrap; original ppm; original eligible available-feature TRAIN arithmetic mean',C1_final_table=False,independent_numeric_readback=False)
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('C1_NMR_ATOMIC_PPRIME_SOURCE_CLOSED',out/'manifest.json','tasks',len(results),flush=True)

PY
C1NMRPPRIME
