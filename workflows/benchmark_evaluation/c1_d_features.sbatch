#!/bin/bash
#SBATCH --job-name=C1-D-shared-feature-prep
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_D_feature_prep_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import json,math,os,unittest
from collections import Counter
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem
from workflows.data_v1_final.labels.common import D20_NAMES
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.shared_reader import SharedB0Reader
from workflows.benchmark_data.task_selection import is_active_task
D3_NAMES=('PMI1','PMI2','PMI3','PBF','volume_A3','SASA_total_A2')
FEATURE_NAMES=list(D20_NAMES)+list(D3_NAMES)
def vector(value):
    if value is None or value.get('D20') is None:return None
    d20=value['D20']
    if d20['names']!=list(D20_NAMES) or len(d20['values'])!=20 or len(d20['valid_mask'])!=20:raise ValueError('Native D20 schema differs')
    numbers=[float(v) if valid and v is not None and math.isfinite(float(v)) else float('nan') for v,valid in zip(d20['values'],d20['valid_mask'])]
    conformers=value.get('conformers') or []
    d3=(conformers[0].get('D3') or {}) if conformers else {}
    numbers += [float(d3[name]) if d3.get(name) is not None and math.isfinite(float(d3[name])) else float('nan') for name in D3_NAMES]
    return numbers
class FeatureTests(unittest.TestCase):
    def fixture(self):return {'D20':{'names':list(D20_NAMES),'values':[float(i) for i in range(20)],'valid_mask':[True]*20},'conformers':[{'D3':dict(zip(D3_NAMES,[1.,2.,3.,4.,5.,6.]))}]}
    def test_native_order_and_first_conformer(self):
        row=self.fixture();row['conformers'].append({'D3':dict.fromkeys(D3_NAMES,999.)})
        self.assertEqual(vector(row),[float(i) for i in range(20)]+[1.,2.,3.,4.,5.,6.])
    def test_missing_geometry_keeps_global_2d_without_fill(self):
        row=self.fixture();row['conformers']=[]
        self.assertEqual(vector(row)[:20],[float(i) for i in range(20)])
        self.assertTrue(all(math.isnan(v) for v in vector(row)[20:]))
    def test_masked_native_field_is_not_zero_imputed(self):
        row=self.fixture();row['D20']['valid_mask'][4]=False
        self.assertTrue(math.isnan(vector(row)[4]))
    def test_entire_missing_result_remains_missing(self):self.assertIsNone(vector(None))
    def test_schema_drift_fails(self):
        row=self.fixture();row['D20']['names']=list(reversed(D20_NAMES))
        with self.assertRaises(ValueError):vector(row)
    def test_nonfinite_native_field_remains_missing(self):
        row=self.fixture();row['conformers'][0]['D3']['PBF']=float('inf')
        self.assertTrue(math.isnan(vector(row)[23]))
suite=unittest.defaultTestLoader.loadTestsFromTestCase(FeatureTests)
if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text())
root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,512*1024**2,quota,own_concurrent_bytes=24*1024**3)
safe()
manifest=json.loads(Path(entry['manifest']).read_text())
catalog_proof=b1/'endpoint_catalog/job_4536889/manifest.json'
assert json.loads(catalog_proof.read_text())['deferred_registry_full_inventory_verified']
out=b1/'C1_D_features'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
schema=pa.schema([('dataset',pa.string()),('source_file',pa.string()),('record_id',pa.string()),('model_smiles',pa.string()),('full_inchikey',pa.string()),('native_shared_molecule_id',pa.string()),('official_split',pa.string()),('retained',pa.bool_()),('domain_eligible',pa.bool_()),('blind_fallback_required',pa.bool_()),('features',pa.list_(pa.float64())),('valid_mask',pa.list_(pa.bool_())),('feature_state',pa.string()),('original_fields_json',pa.string())])
cache={};summaries=[];pending_reference=[]
with SharedB0Reader(manifest['Sprime_and_D']['queue']) as reader:
    for group,spec in manifest['source_groups'].items():
        if group in ('C7H10O2','PPE1694','NMRShiftDB2'):
            pending_reference.append(group);continue
        counts=Counter();target=out/(group+'.parquet')
        with pq.ParquetWriter(target,schema,compression='zstd') as sink:
            for batch in pq.ParquetFile(spec['records']).iter_batches(batch_size=1024):
                output=[]
                for row in batch.to_pylist():
                    if not is_active_task(group,row['source_file']):continue
                    counts['active_source_rows']+=1
                    smiles=row['model_smiles'];features=None;mid=None;key=None
                    state='OUTSIDE_DOMAIN_NO_C1_LABEL_IMPUTATION'
                    if row['domain_eligible']:
                        if smiles not in cache:
                            try:
                                native=reader.get(group,row['record_id'])
                                values=vector(native['result']);native_mid=native['shared_molecule_id']
                                feature_state='NATIVE_D26_AVAILABLE' if values is not None else 'NATIVE_D_LABELS_MISSING'
                            except KeyError:
                                values=None;native_mid=None;feature_state='NATIVE_MEMBERSHIP_MISSING'
                            mol=Chem.MolFromSmiles(smiles);inchi=Chem.MolToInchiKey(mol) if mol is not None else None
                            cache[smiles]=(values,native_mid,inchi,feature_state)
                        features,mid,key,state=cache[smiles]
                    valid=None if features is None else [math.isfinite(x) for x in features]
                    if valid is not None and not all(valid):state='NATIVE_D26_PARTIAL_NO_IMPUTATION'
                    counts[state]+=1
                    output.append({'dataset':group,'source_file':row['source_file'],'record_id':row['record_id'],'model_smiles':smiles,'full_inchikey':key,'native_shared_molecule_id':mid,'official_split':row['official_split'],'retained':row['retained'],'domain_eligible':row['domain_eligible'],'blind_fallback_required':row['blind_fallback_required'],'features':features,'valid_mask':valid,'feature_state':state,'original_fields_json':row['original_fields_json']})
                safe()
                if output:sink.write_table(pa.Table.from_pylist(output,schema=schema))
        summaries.append({'dataset':group,'features':str(target),'counts':dict(counts)})
        print('C1_D_FEATURE_SOURCE_CLOSED',group,json.dumps(dict(counts)),flush=True)
report={'status':'C1_D_SHARED_FEATURE_PREPARATION_CLOSED_FOR_EIGHT_TABULAR_GROUPS','job':os.environ['SLURM_JOB_ID'],'new_logic_unit_tests':suite.countTestCases(),'source_entry':str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),'full_inventory_scope_proof':str(catalog_proof),'feature_names':FEATURE_NAMES,'D20_source':'Unchanged shared B0 original raw F64 values and masks','D3_source':'Six native shared B0 D_native_3D molecular scalars on first accepted S-prime UFF conformer; atomic SASA stays an atom-level feature, not a separate invented molecular target','geometry':'Same first accepted shared UFF conformer used by B2 smoke; no generation or numerical recomputation','missing_policy':'NaN plus explicit valid mask; wholly unavailable feature vectors stay null; no filling','normalization_fitted':False,'source_groups':summaries,'reference_group_bindings_pending':pending_reference,'model_fits_run':False,'C1_final_results_produced':False,'no_database_copies':True}
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('C1_D_FEATURE_MANIFEST',out/'manifest.json',flush=True)
PY
