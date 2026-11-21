#!/bin/bash
#SBATCH --job-name=B1-PPE-fixed-scaffold-CV-binding
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_reference_CV_binding_%j.log
set -euo pipefail
export BENCHMARK_GROUPS=PPE1694
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
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from workflows.benchmark_data.admission import protect
SEED=20261025
class IncompleteComparison(ValueError):pass
def scaffold_folds(scaffold_groups, seed=SEED):
    """Yield five repetitions of five disjoint scaffold-group folds."""
    groups = np.asarray(scaffold_groups, dtype=str)
    unique, inverse = np.unique(groups, return_inverse=True)
    if len(unique) < 5:
        raise IncompleteComparison("Fewer than five scaffolds; do not replace with a random split")
    members = [np.flatnonzero(inverse == index) for index in range(len(unique))]
    streams = np.random.SeedSequence(seed).spawn(5)
    for repetition, stream in enumerate(streams):
        rng = np.random.default_rng(stream)
        order = rng.permutation(len(unique))
        assignments = [[] for _ in range(5)]
        sizes = np.zeros(5, dtype=int)
        for index in order:
            candidates = np.flatnonzero(sizes == sizes.min())
            fold = int(rng.choice(candidates))
            assignments[fold].extend(members[index].tolist())
            sizes[fold] += len(members[index])
        for fold, selected in enumerate(assignments):
            test = np.sort(np.asarray(selected, dtype=int))
            train = np.setdiff1d(np.arange(len(groups)), test)
            if not len(train) or not len(test):
                raise IncompleteComparison("Empty scaffold fold; no split substitution allowed")
            yield repetition, fold, train, test


def finite(value):
    try:number=float(value)
    except (TypeError,ValueError):return None
    return number if math.isfinite(number) else None
def c7_targets(row):
    return {'G4MP2_absolute':finite(row['G4MP2_absolute_hartree']),'G4MP2_minus_B3LYP':finite(row['delta_G4MP2_minus_B3LYP_hartree'])}
class NativeTargetTests(unittest.TestCase):
    def test_original_C7_entry_absent_from_primary_is_not_automatically_dropped(self):
        row=dict(primary_record_available=False,gdb9_index=6001,G4MP2_absolute_hartree=-100.,delta_G4MP2_minus_B3LYP_hartree=.1)
        self.assertEqual(c7_targets(row),{'G4MP2_absolute':-100.,'G4MP2_minus_B3LYP':.1})
    def test_native_missing_delta_is_not_reconstructed(self):
        self.assertIsNone(c7_targets(dict(G4MP2_absolute_hartree=-100.,delta_G4MP2_minus_B3LYP_hartree=None))['G4MP2_minus_B3LYP'])
    def test_scaffold_is_never_shared_between_train_and_test(self):
        groups=['a','a','b','c','d','e','f','g']
        folds=list(scaffold_folds(groups))
        self.assertEqual(len(folds),25)
        for repetition,fold,train,test in folds:self.assertFalse({groups[i] for i in train}&{groups[i] for i in test})
tests=unittest.defaultTestLoader.loadTestsFromTestCase(NativeTargetTests)
if not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,128*1024**2,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'reference_cv_binding'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
features=b1/'reference_features/job_4536983';contract=json.loads((features/'manifest.json').read_text())
proof=json.loads(Path(contract['full_inventory_scope_proof']).read_text());assert proof['deferred_registry_full_inventory_verified'] and proof['deferred_endpoint_count']==5
manifest=json.loads(Path(entry['manifest']).read_text());reports=[]
groups=tuple(os.environ.get('BENCHMARK_GROUPS','C7H10O2').split(','))
if not groups or set(groups)-{'C7H10O2','PPE1694'}:raise ValueError('Unknown reference dataset')
label_schema=pa.schema([('dataset',pa.string()),('task',pa.string()),('record_id',pa.string()),('full_inchikey',pa.string()),('scaffold_group',pa.string()),('y',pa.float64()),('unit',pa.string()),('quantity',pa.string()),('retained',pa.bool_()),('domain_eligible',pa.bool_())])
fold_schema=pa.schema([('dataset',pa.string()),('repetition',pa.int32()),('fold',pa.int32()),('record_id',pa.string()),('scaffold_group',pa.string()),('split',pa.string()),('retained',pa.bool_()),('domain_eligible',pa.bool_())])
for group in groups:
    source=features/(group+'.parquet');records=pq.read_table(source).to_pylist()
    if group=='C7H10O2':
        target_manifest=Path(manifest['C7_targets']);native=json.loads(target_manifest.read_text());target_path=Path(native['records'])
        values=pq.read_table(target_path).to_pylist();targets={r['record_id']:r for r in values}
    else:
        target_manifest=b1/'PPE_Benson/job_4536988/manifest.json';native=json.loads(target_manifest.read_text());target_path=Path(native['records'])
        values=pq.read_table(target_path).to_pylist();targets={r['record_id']:r for r in values}
    if len(targets)!=len(values):raise ValueError('Ambiguous native target record')
    processable=[];counts=Counter();labels=[];target_counts=defaultdict(Counter)
    for row in records:
        counts['source_molecules']+=1
        if row['record_id'] not in targets:raise ValueError('Reference target identity is not source-bound')
        target=targets[row['record_id']]
        if row['ecfp4_2048_packed'] is None or not row['full_inchikey']:
            counts['unresolved_source_graph_or_full_identity']+=1;continue
        mol=Chem.MolFromSmiles(row['feature_smiles'])
        if mol is None:raise ValueError('Closed feature graph unavailable for scaffold binding')
        scaffold=MurckoScaffold.MurckoScaffoldSmiles(mol=mol,includeChirality=False) or 'ACYCLIC'
        processable.append(dict(row,scaffold_group=scaffold));counts['processable_source_molecules']+=1
        endpoint_values=c7_targets(target) if group=='C7H10O2' else {'delta_Hf_minus_group_additivity':finite(target['residual_experimental_minus_BensonGA_kcal_mol']),'delta_Hf_minus_semiempirical':finite(target['residual_experimental_minus_published_PM7_kcal_mol'])}
        for task,y in endpoint_values.items():
            if y is None:target_counts[task]['native_label_missing']+=1;continue
            retained=bool(row['retained'] and row['domain_eligible'])
            target_counts[task]['total_labeled_points']+=1;target_counts[task]['filtered_labeled_points']+=retained
            labels.append(dict(dataset=group,task=task,record_id=row['record_id'],full_inchikey=row['full_inchikey'],scaffold_group=scaffold,y=y,unit='hartree' if group=='C7H10O2' else 'kcal/mol',quantity=('G298 absolute G4MP2' if task=='G4MP2_absolute' else 'G298 G4MP2 minus B3LYP') if group=='C7H10O2' else task,retained=row['retained'],domain_eligible=row['domain_eligible']))
    safe();label_path=out/(group+'_endpoint_rows.parquet');pq.write_table(pa.Table.from_pylist(labels,schema=label_schema),label_path,compression='zstd')
    fold_path=out/(group+'_scaffold_folds.parquet');fold_counts=[];status='FIXED_FIVE_BY_FIVE_SCAFFOLD_FOLDS_CLOSED'
    try:
        folds=list(scaffold_folds([r['scaffold_group'] for r in processable]))
        with pq.ParquetWriter(fold_path,fold_schema,compression='zstd') as writer:
            # Each molecule receives exactly one test fold per repetition.
            for repetition,fold,train,test in folds:
                fold_counts.append(dict(repetition=repetition,fold=fold,full_train=len(train),full_test=len(test),retained_train=sum(processable[i]['retained'] and processable[i]['domain_eligible'] for i in train),retained_test=sum(processable[i]['retained'] and processable[i]['domain_eligible'] for i in test)))
                output=[dict(dataset=group,repetition=repetition,fold=fold,record_id=processable[i]['record_id'],scaffold_group=processable[i]['scaffold_group'],split=split,retained=processable[i]['retained'],domain_eligible=processable[i]['domain_eligible']) for split,indices in (('train',train),('test',test)) for i in indices]
                safe();writer.write_table(pa.Table.from_pylist(output,schema=fold_schema))
    except IncompleteComparison as error:status='UNRESOLVED_SCAFFOLD_PROTOCOL';counts['scaffold_protocol_error']=str(error)
    reports.append(dict(dataset=group,status=status,features=str(source),original_native_targets=str(target_path),original_target_manifest=str(target_manifest),official_endpoint_labels=str(label_path),scaffold_folds=str(fold_path) if status=='FIXED_FIVE_BY_FIVE_SCAFFOLD_FOLDS_CLOSED' else None,source_counts=dict(counts),endpoint_counts={k:dict(v) for k,v in target_counts.items()},fold_counts=fold_counts))
    print('REFERENCE_CV_BINDING_CLOSED',group,status,json.dumps({k:dict(v) for k,v in target_counts.items()}),flush=True)
report=dict(status='REFERENCE_NATIVE_TARGETS_AND_SCAFFOLD_FOLDS_BOUND',job=os.environ['SLURM_JOB_ID'],source_entry=str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),source_contract=str(features/'manifest.json'),full_inventory_scope_proof=contract['full_inventory_scope_proof'],source_groups=reports,fold_seed=SEED,fold_protocol='Five SeedSequence child streams; random whole-scaffold order; greedy balancing to smallest fold with seeded tie handling; no individual molecule random split',scaffold_recipe='RDKit MurckoScaffoldSmiles includeChirality=False; all acyclic source graphs share ACYCLIC group',fold_population='Fixed full-source graph population before target/domain eligibility masking; same membership for full and retained diagnostics and all models',model_fits_run=False,task_screen_decisions_produced=False,new_unit_tests=tests.countTestCases(),independent_numeric_readback=False)
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('REFERENCE_CV_MANIFEST',out/'manifest.json',flush=True)

PY
