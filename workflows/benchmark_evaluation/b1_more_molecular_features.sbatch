#!/bin/bash
#SBATCH --job-name=B1-RDKit-ECFP-next-five-groups
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_more_features_%j.log
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
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text())
root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,1024**3,quota,own_concurrent_bytes=24*1024**3)
safe()
manifest=json.loads(Path(entry['manifest']).read_text())
proof_path=b1/'endpoint_catalog/job_4536889/manifest.json';proof=json.loads(proof_path.read_text())
assert proof['deferred_registry_full_inventory_verified']
fingerprints=load_deferred_policy()
out=b1/'B1_molecular_features'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
schema=pa.schema([('dataset',pa.string()),('source_file',pa.string()),('record_id',pa.string()),('model_smiles',pa.string()),('feature_smiles',pa.string()),('full_inchikey',pa.string()),('official_split',pa.string()),('retained',pa.bool_()),('domain_eligible',pa.bool_()),('blind_fallback_required',pa.bool_()),('ecfp4_2048_packed',pa.binary()),('rdkit_2d',pa.list_(pa.float64())),('feature_state',pa.string()),('original_fields_json',pa.string())])
cache={};sources=[]
# Reuse the exact closed feature bytes as a consumer cache, without numerical rechecking.
previous=b1/'B1_molecular_features/job_4536908'
for previous_group in ('MoleculeACE','PharmaBench'):
    for batch in pq.ParquetFile(previous/(previous_group+'.parquet')).iter_batches(batch_size=2048,columns=['feature_smiles','ecfp4_2048_packed','rdkit_2d','full_inchikey']):
        for row in batch.to_pylist():
            cache[row['feature_smiles']]=None if row['ecfp4_2048_packed'] is None else (row['ecfp4_2048_packed'],row['rdkit_2d'],row['full_inchikey'])
groups=[group for group in manifest['source_groups'] if group not in ('MoleculeACE','PharmaBench','pKahub','C7H10O2','PPE1694','NMRShiftDB2')]
assert len(groups)==5
for group in groups:
    spec=manifest['source_groups'][group];counts=Counter();target=out/(group+'.parquet')
    with pq.ParquetWriter(target,schema,compression='zstd') as writer:
        for batch in pq.ParquetFile(spec['records']).iter_batches(batch_size=512):
            output=[]
            for row in batch.to_pylist():
                if not is_active_task(group,row['source_file'],fingerprints=fingerprints):continue
                counts['active_source_rows']+=1
                smiles=row['model_smiles'] or row['original_smiles']
                if smiles not in cache:cache[smiles]=featurize(smiles)
                value=cache[smiles]
                if value is None:
                    packed=descriptors=key=None;state='UNPARSEABLE_GRAPH'
                else:
                    packed,descriptors,key=value;state='FEATURES_READY' if all(math.isfinite(x) for x in descriptors) else 'RDKit_PARTIAL_NATIVE_MISSING_VALUES'
                counts[state]+=1
                output.append({'dataset':group,'source_file':row['source_file'],'record_id':row['record_id'],'model_smiles':row['model_smiles'],'feature_smiles':smiles,'full_inchikey':key,'official_split':row['official_split'],'retained':row['retained'],'domain_eligible':row['domain_eligible'],'blind_fallback_required':row['blind_fallback_required'],'ecfp4_2048_packed':packed,'rdkit_2d':descriptors,'feature_state':state,'original_fields_json':row['original_fields_json']})
            safe()
            if output:writer.write_table(pa.Table.from_pylist(output,schema=schema))
    sources.append({'dataset':group,'features':str(target),'counts':dict(counts)})
    print('B1_MOLECULAR_FEATURE_SOURCE_CLOSED',group,json.dumps(dict(counts)),flush=True)
report={'status':'B1_MOLECULAR_FEATURES_READY_FOR_FIVE_ADDITIONAL_SOURCE_GROUPS','job':os.environ['SLURM_JOB_ID'],'unit_tests':suite.countTestCases(),'source_entry':str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),'scope_proof':str(proof_path),'reused_feature_cache':str(previous/'manifest.json'),'rdkit_version':rdBase.rdkitVersion,'ecfp4':{'radius':2,'bits':2048,'include_chirality':False,'encoding':'RDKit BitVectToBinaryText, 256 bytes'},'rdkit_2d_names':[name for name,_ in DESCRIPTORS],'rdkit_2d_count':len(DESCRIPTORS),'descriptor_missing_policy':'Native calculation errors/nonfinite values stay NaN; no zero fill','filter_impact_support':'All active source rows retained in this derived feature product, with original retained/domain flags; models can report full/retained/excluded populations','source_groups':sources,'model_fits_run':False,'B1_task_screen_produced':False,'other_source_groups_still_required':True,'no_database_copies':True}
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('B1_MOLECULAR_FEATURE_MANIFEST',out/'manifest.json',flush=True)
PY
