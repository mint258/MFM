#!/bin/bash
#SBATCH --job-name=Joung-declared-gas-context-overlay
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/Joung_gas_context_%j.log
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
from collections import Counter,defaultdict
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem,DataStructs
from rdkit.Chem import Descriptors,rdFingerprintGenerator
from workflows.benchmark_data.admission import protect
DESCRIPTORS=list(Descriptors._descList);GENERATOR=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=False)
def absent_solvent_features():
    mol=Chem.MolFromSmiles('')
    values=[]
    for name,function in DESCRIPTORS:
        try:value=float(function(mol))
        except Exception:value=float('nan')
        values.append(value if math.isfinite(value) else float('nan'))
    return DataStructs.BitVectToBinaryText(GENERATOR.GetFingerprint(mol)),values
class GasConditionTests(unittest.TestCase):
    def test_declared_gas_condition_has_no_solvent_atoms_or_fingerprint_bits(self):
        self.assertEqual(Chem.MolFromSmiles('').GetNumAtoms(),0)
        fp,values=absent_solvent_features()
        self.assertEqual(len(fp),256);self.assertEqual(sum(fp),0);self.assertEqual(len(values),len(DESCRIPTORS))
    def test_undefined_empty_graph_descriptors_stay_missing(self):
        fp,values=absent_solvent_features()
        self.assertTrue(any(math.isnan(value) for value in values))
tests=unittest.defaultTestLoader.loadTestsFromTestCase(GasConditionTests)
if not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,2*1024**3,quota,own_concurrent_bytes=40*1024**3)
safe();out=b1/'Joung_gas_context'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
parent_path=b1/'Joung_components/job_4537012/manifest.json';parent=json.loads(parent_path.read_text())
if set(parent['unresolved_source_solvent_lexemes'])-{'gas'}:raise ValueError('Unknown solvent context must remain unresolved')
assert parent['chromophore_and_solvent_component_descriptor_names']==[name for name,_ in DESCRIPTORS]
oldspec=parent['source_groups'][0];table=pq.read_table(oldspec['features']);records=table.to_pylist()
gas_ids={r['record_id'] for r in records if r['solvent_smiles']=='gas'}
chromophore_cache={}
for batch in pq.ParquetFile(b1/'B1_molecular_features/job_4536920/Joung2020.parquet').iter_batches(batch_size=1024,columns=['record_id','rdkit_2d']):
    for row in batch.to_pylist():
        if row['record_id'] in gas_ids:chromophore_cache[row['record_id']]=row['rdkit_2d']
gas_fp,gas_rdkit=absent_solvent_features();ENDPOINTS=('Absorption max (nm)','Emission max (nm)','Lifetime (ns)','Quantum yield','log(e/mol-1 dm3 cm-1)','abs FWHM (cm-1)','emi FWHM (cm-1)','abs FWHM (nm)','emi FWHM (nm)')
label_table=pq.read_table(oldspec['official_endpoint_labels']);labels=label_table.to_pylist();counts=Counter()
for row in records:
    gas=row['solvent_smiles']=='gas';row['is_gas']=gas
    if gas:
        row['solvent_smiles']='';row['solvent_ecfp4_2048_packed']=gas_fp;row['solvent_rdkit_2d']=gas_rdkit
        row['rdkit_2d']=chromophore_cache[row['record_id']]+gas_rdkit+[1.]
        native_D=row['native_chromophore_D_features']
        row['D_features']=native_D+gas_rdkit+[1.] if native_D is not None else None
        row['input_ready']=True;counts['original_gas_observations_bound']+=1
        raw=json.loads(row['original_fields_json'])
        for task in ENDPOINTS:
            try:y=float(raw.get(task))
            except (ValueError,TypeError):continue
            if not math.isfinite(y):continue
            labels.append(dict(dataset='Joung2020',task=task,record_id=row['record_id'],full_inchikey=row['full_inchikey'],scaffold_group=row['scaffold_group'],y=y,retained=row['retained'],domain_eligible=row['domain_eligible']))
    else:
        if row['rdkit_2d'] is not None:row['rdkit_2d']=row['rdkit_2d']+[0.]
        if row['D_features'] is not None:row['D_features']=row['D_features']+[0.]
    counts['all_original_source_observations']+=1;counts['input_ready']+=row['input_ready']
schema=pa.schema(list(table.schema)+[pa.field('is_gas',pa.bool_())])
safe();feature_path=out/'Joung2020.parquet';label_path=out/'Joung2020_endpoint_rows.parquet'
pq.write_table(pa.Table.from_pylist(records,schema=schema),feature_path,compression='zstd');pq.write_table(pa.Table.from_pylist(labels,schema=label_table.schema),label_path,compression='zstd')
endpoint_counts=defaultdict(Counter)
for row in labels:
    endpoint_counts[row['task']]['total_labeled_points']+=1;endpoint_counts[row['task']]['filtered_labeled_points']+=bool(row['retained'] and row['domain_eligible'])
spec=dict(oldspec,features=str(feature_path),official_endpoint_labels=str(label_path),endpoint_counts={k:dict(v) for k,v in endpoint_counts.items()},source_counts=dict(counts))
report=dict(status='JOUNG_DECLARED_GAS_PHASE_CONTEXT_BOUND_WITHOUT_SOURCE_LABEL_CHANGES',job=os.environ['SLURM_JOB_ID'],source_entry=str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),parent_feature_binding=str(parent_path),full_inventory_scope_proof=parent['full_inventory_scope_proof'],source_groups=[spec],counts=dict(counts),RF_features='Separate chromophore2048 + solvent2048 Morgan blocks + explicit is_gas indicator; empty solvent fingerprint is the native fingerprint of a zero-atom graph',LightGBM_features='Chromophore RDKit2D + solvent RDKit2D + is_gas; undefined empty-solvent descriptors remain native NaN',Chemprop_features='Official MulticomponentMPNN supports a native zero-atom solvent graph, with explicit is_gas in X_d; no dummy chemical atom or geometry',C1_D_features='Unchanged native chromophore D26 plus same solvent RDKit2D and is_gas context; original missing native D remains absent',original_gas_lexeme='gas',gas_is_declared_source_condition_not_missing_solvent=True,original_B0_domain_flags_unchanged=True,original_labels_unchanged=True,original_fixed_scaffold_folds_reused=oldspec['scaffold_folds'],new_conformers_generated=False,new_unit_tests=tests.countTestCases(),model_fits_run=False,task_screen_decisions_produced=False,independent_numeric_readback=False)
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('JOUNG_GAS_CONTEXT_CLOSED',json.dumps(report),flush=True)

PY
