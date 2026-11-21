#!/bin/bash
#SBATCH --job-name=C1-D-B1-reference-feature-binding
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_reference_features_%j.log
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
from pathlib import Path
from collections import Counter
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem,DataStructs,rdBase,RDLogger
from rdkit.Chem import Descriptors,rdFingerprintGenerator
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.task_selection import is_active_task,load_deferred_policy
RDLogger.DisableLog('rdApp.error')
GENERATOR=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=False)
DESCRIPTORS=list(Descriptors._descList)
def descriptor_values(mol,functions):
    values=[]
    for name,function in functions:
        try:value=float(function(mol))
        except Exception:value=float('nan')
        values.append(value if math.isfinite(value) else float('nan'))
    return values
def featurize(smiles):
    mol=Chem.MolFromSmiles(smiles) if smiles else None
    if mol is None:return None
    fingerprint=DataStructs.BitVectToBinaryText(GENERATOR.GetFingerprint(mol))
    return fingerprint,descriptor_values(mol,DESCRIPTORS),Chem.MolToInchiKey(mol)
class FeatureTests(unittest.TestCase):
    def test_fingerprint_has_2048_bits_and_roundtrips(self):
        packed,_,_=featurize('CCO')
        self.assertEqual(len(packed),256)
        restored=DataStructs.CreateFromBinaryText(packed)
        self.assertEqual(restored.GetNumBits(),2048)
        self.assertEqual(restored,GENERATOR.GetFingerprint(Chem.MolFromSmiles('CCO')))
    def test_nonchiral_ecfp_does_not_change_structural_identity(self):
        left=featurize('C[C@H](O)Cl');right=featurize('C[C@@H](O)Cl')
        self.assertEqual(left[0],right[0]);self.assertNotEqual(left[2],right[2])
    def test_invalid_graph_is_explicitly_missing(self):self.assertIsNone(featurize('not a molecule'))
    def test_descriptor_exception_and_infinity_are_missing_not_zero(self):
        def broken(mol):raise ValueError('unsupported')
        values=descriptor_values(Chem.MolFromSmiles('CCO'),[('a',lambda m:2.),('b',broken),('c',lambda m:float('inf')),('d',lambda m:4.)])
        self.assertEqual(values[0],2.);self.assertTrue(math.isnan(values[1]));self.assertTrue(math.isnan(values[2]));self.assertEqual(values[3],4.)
    def test_descriptor_order_is_recorded(self):
        _,values,_=featurize('CCO');self.assertEqual(len(values),len(DESCRIPTORS))
        self.assertEqual([name for name,_ in DESCRIPTORS].count('MolWt'),1)
suite=unittest.defaultTestLoader.loadTestsFromTestCase(FeatureTests)
if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():raise SystemExit(1)

from workflows.data_v1_final.labels.common import D20_NAMES
D3_NAMES=('PMI1','PMI2','PMI3','PBF','volume_A3','SASA_total_A2')
def native_D(d20,d3):
    values=[float('nan')]*26;valid=[False]*26
    if d20 is not None:
        if list(d20['D20_names'])!=list(D20_NAMES):raise ValueError('Native D20 feature order differs from the frozen pretraining fields')
        if len(d20['D20_values'])!=20 or len(d20['D20_valid_mask'])!=20:raise ValueError('Incomplete native D20 interface')
        for index,(value,mask) in enumerate(zip(d20['D20_values'],d20['D20_valid_mask'])):
            if mask and value is not None and math.isfinite(value):values[index]=float(value);valid[index]=True
    if d3 is not None:
        masks=d3['D3_valid_mask'] or []
        for index,name in enumerate(D3_NAMES):
            value=d3.get(name)
            if len(masks)>index and masks[index] and value is not None and math.isfinite(value):values[index+20]=float(value);valid[index+20]=True
    return (values if any(valid) else None),valid
class NativeDTests(unittest.TestCase):
    def test_missing_native_D_is_not_zero_filled(self):
        values,valid=native_D(None,None);self.assertIsNone(values);self.assertFalse(any(valid))
    def test_invalid_native_scalar_stays_missing(self):
        d3={name:float(i) for i,name in enumerate(D3_NAMES)};d3['D3_valid_mask']=[False,True,True,True,True,True,True]
        values,valid=native_D(None,d3);self.assertTrue(math.isnan(values[20]));self.assertFalse(valid[20]);self.assertEqual(values[21],1.)
    def test_D20_order_is_a_binding_contract(self):
        with self.assertRaises(ValueError):native_D({'D20_names':[],'D20_values':[],'D20_valid_mask':[]},None)
native_tests=unittest.defaultTestLoader.loadTestsFromTestCase(NativeDTests)
if not unittest.TextTestRunner(verbosity=2).run(native_tests).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,1024**3,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'reference_features'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
manifest=json.loads(Path(entry['manifest']).read_text());proof_path=b1/'endpoint_catalog/job_4536889/manifest.json';proof=json.loads(proof_path.read_text());assert proof['deferred_registry_full_inventory_verified']
d20_sources={spec['dataset']:spec['records'] for spec in manifest['reference_D20']['groups']}
d3_sources={}
for path in manifest['reference_D3']['manifests']:
    report=json.loads(Path(path).read_text())
    for group in report.get('groups',[report]):
        dataset=group['dataset']
        if dataset in d3_sources:raise ValueError('Ambiguous reference D3 producer; consume the B0 closure contract explicitly')
        d3_sources[dataset]=group['records']
schema=pa.schema([('dataset',pa.string()),('source_file',pa.string()),('record_id',pa.string()),('source_row',pa.int64()),('model_smiles',pa.string()),('feature_smiles',pa.string()),('full_inchikey',pa.string()),('retained',pa.bool_()),('domain_eligible',pa.bool_()),('exclusion_reasons',pa.list_(pa.string())),('official_split',pa.string()),('ecfp4_2048_packed',pa.binary()),('rdkit_2d',pa.list_(pa.float64())),('D_features',pa.list_(pa.float64())),('D_valid_mask',pa.list_(pa.bool_())),('D3_state',pa.string()),('original_fields_json',pa.string())])
cache={};sources=[]
for group in ('C7H10O2','PPE1694'):
    d20={row['record_id']:row for row in pq.read_table(d20_sources[group]).to_pylist()}
    d3={row['record_id']:row for row in pq.read_table(d3_sources[group]).to_pylist()}
    target=out/(group+'.parquet');counts=Counter()
    with pq.ParquetWriter(target,schema,compression='zstd') as writer:
        for batch in pq.ParquetFile(manifest['source_groups'][group]['records']).iter_batches(batch_size=512):
            buffer=[]
            for row in batch.to_pylist():
                counts['source_rows']+=1;counts['domain_eligible']+=row['domain_eligible']
                smiles=row['model_smiles'] or row['original_smiles']
                if smiles not in cache:cache[smiles]=featurize(smiles)
                encoded=cache[smiles]
                if encoded is None:fp=rdkit2d=key=None;counts['unparseable_2D_graph']+=1
                else:fp,rdkit2d,key=encoded;counts['2D_features_available']+=1
                values,valid=native_D(d20.get(row['record_id']),d3.get(row['record_id']))
                counts['native_D_rows_available']+=values is not None
                counts['native_D_complete_rows']+=all(valid)
                buffer.append({'dataset':group,'source_file':row['source_file'],'record_id':row['record_id'],'source_row':row['source_row'],'model_smiles':row['model_smiles'],'feature_smiles':smiles,'full_inchikey':key,'retained':row['retained'],'domain_eligible':row['domain_eligible'],'exclusion_reasons':row['exclusion_reasons'],'official_split':row['official_split'],'ecfp4_2048_packed':fp,'rdkit_2d':rdkit2d,'D_features':values,'D_valid_mask':valid,'D3_state':d3.get(row['record_id'],{}).get('state','NO_NATIVE_D3_RECORD'),'original_fields_json':row['original_fields_json']})
            safe()
            if buffer:writer.write_table(pa.Table.from_pylist(buffer,schema=schema))
    sources.append({'dataset':group,'records':str(target),'counts':dict(counts),'native_D20':d20_sources[group],'native_D3':d3_sources[group]})
    print('REFERENCE_NATIVE_FEATURE_SOURCE_CLOSED',group,json.dumps(dict(counts)),flush=True)
report={'status':'C7_PPE_MOLECULAR_NATIVE_D_AND_B1_2D_FEATURES_CLOSED','job':os.environ['SLURM_JOB_ID'],'source_entry':str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),'full_inventory_scope_proof':str(proof_path),'source_groups':sources,'D_feature_names':list(D20_NAMES)+list(D3_NAMES),'rdkit_2d_names':[name for name,_ in DESCRIPTORS],'unit_tests':suite.countTestCases()+native_tests.countTestCases(),'reference_geometry':'Original dataset reference; no UFF substitution or new geometry generation','native_D_recomputed':False,'native_F64_unchanged':True,'invalid_native_values':'NaN plus original validity mask; no zero/mean fill','C7_targets':manifest['C7_targets'],'PPE_targets':manifest['PPE_targets'],'PPE_Benson_residual_binding_still_required':True,'splits_and_model_fits_run':False,'B1_task_screen_decisions_produced':False,'independent_numeric_readback':False}
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('REFERENCE_FEATURE_BINDING_CLOSED',out/'manifest.json',flush=True)

PY
