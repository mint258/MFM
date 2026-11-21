#!/bin/bash
#SBATCH --job-name=B1-Joung-two-component-feature-binding
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=02:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_Joung_features_%j.log
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
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem,DataStructs,rdBase,RDLogger
from rdkit.Chem import Descriptors,rdFingerprintGenerator
from rdkit.Chem.Scaffolds import MurckoScaffold
from workflows.benchmark_data.admission import protect
RDLogger.DisableLog('rdApp.error')
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


ENDPOINTS=('Absorption max (nm)','Emission max (nm)','Lifetime (ns)','Quantum yield','log(e/mol-1 dm3 cm-1)','abs FWHM (cm-1)','emi FWHM (cm-1)','abs FWHM (nm)','emi FWHM (nm)')
def finite(value):
    try:value=float(value)
    except (ValueError,TypeError):return None
    return value if math.isfinite(value) else None
def component_features(smiles):
    mol=Chem.MolFromSmiles(smiles) if smiles else None
    if mol is None:return None
    values=[]
    for name,function in DESCRIPTORS:
        try:value=float(function(mol))
        except Exception:value=float('nan')
        values.append(value if math.isfinite(value) else float('nan'))
    return DataStructs.BitVectToBinaryText(GENERATOR.GetFingerprint(mol)),values
DESCRIPTORS=list(Descriptors._descList);GENERATOR=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=False)
class ComponentBindingTests(unittest.TestCase):
    def test_solvent_is_separate_even_when_smaller_than_chromophore_domain(self):
        value=component_features('O')
        self.assertIsNotNone(value);self.assertEqual(len(value[0]),256)
    def test_missing_solvent_is_not_guessed_or_filled(self):
        self.assertIsNone(component_features(None));self.assertIsNone(component_features('unknown solvent'))
    def test_all_solvent_observations_of_one_scaffold_stay_in_the_same_fold(self):
        groups=['chromA','chromA','chromB','chromC','chromD','chromE','chromF']
        for rep,fold,train,test in scaffold_folds(groups):self.assertEqual(0 in test,1 in test)
tests=unittest.defaultTestLoader.loadTestsFromTestCase(ComponentBindingTests)
if not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,2*1024**3,quota,own_concurrent_bytes=40*1024**3)
safe();out=b1/'Joung_components'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
manifest=json.loads(Path(entry['manifest']).read_text());source=Path(manifest['source_groups']['Joung2020']['records'])
base_features=b1/'B1_molecular_features/job_4536920';base_contract=json.loads((base_features/'manifest.json').read_text())
proof_path=Path(base_contract['scope_proof']);proof=json.loads(proof_path.read_text());assert proof['deferred_registry_full_inventory_verified'] and proof['deferred_endpoint_count']==5 and proof['candidate_counts_by_source_group']['Joung2020']==9
features={r['record_id']:r for r in pq.read_table(base_features/'Joung2020.parquet').to_pylist()}
D_root=b1/'C1_D_features/job_4536892';D_contract=json.loads((D_root/'manifest.json').read_text())
D_rows={r['record_id']:r for r in pq.read_table(D_root/'Joung2020.parquet').to_pylist()}
cache={};counts=Counter();unresolved_solvents=Counter();target_counts=defaultdict(Counter);labels=[];records=[]
for batch in pq.ParquetFile(source).iter_batches(batch_size=1024):
    for native in batch.to_pylist():
        row=features[native['record_id']];raw=json.loads(native['original_fields_json']);solvent=str(raw.get('Solvent') or '').strip()
        if solvent not in cache:cache[solvent]=component_features(solvent)
        value=cache[solvent];counts['source_observations']+=1
        graph_ready=row['ecfp4_2048_packed'] is not None and bool(row['full_inchikey'])
        input_ready=graph_ready and value is not None
        if value is None:unresolved_solvents[solvent]+=1
        if not graph_ready:counts['unresolved_chromophore_graph_or_full_identity']+=1
        solvent_fp,solvent_rdkit=value if value is not None else (None,None)
        chrom_mol=Chem.MolFromSmiles(row['feature_smiles']) if graph_ready else None
        scaffold=(MurckoScaffold.MurckoScaffoldSmiles(mol=chrom_mol,includeChirality=False) or 'ACYCLIC') if chrom_mol is not None else None
        D=D_rows[native['record_id']]['features'];Dcombined=(D+solvent_rdkit) if D is not None and solvent_rdkit is not None else None
        record=dict(dataset='Joung2020',record_id=row['record_id'],source_row=native['source_row'],feature_smiles=row['feature_smiles'],solvent_smiles=solvent,full_inchikey=row['full_inchikey'],scaffold_group=scaffold,retained=row['retained'],domain_eligible=row['domain_eligible'],exclusion_reasons=native['exclusion_reasons'],ecfp4_2048_packed=row['ecfp4_2048_packed'],solvent_ecfp4_2048_packed=solvent_fp,rdkit_2d=(row['rdkit_2d']+solvent_rdkit) if row['rdkit_2d'] is not None and solvent_rdkit is not None else None,D_features=Dcombined,native_chromophore_D_features=D,solvent_rdkit_2d=solvent_rdkit,input_ready=input_ready,original_fields_json=native['original_fields_json'])
        records.append(record);counts['two_component_input_ready']+=input_ready
        for task in ENDPOINTS:
            y=finite(raw.get(task))
            if y is None:target_counts[task]['missing_or_unparsed_original_label']+=1;continue
            target_counts[task]['original_labeled_points']+=1
            target_counts[task]['domain_filtered_labeled_points']+=bool(row['retained'] and row['domain_eligible'])
            if not input_ready:target_counts[task]['unresolved_original_two_component_input_points']+=1;continue
            labels.append(dict(dataset='Joung2020',task=task,record_id=row['record_id'],full_inchikey=row['full_inchikey'],scaffold_group=scaffold,y=y,retained=row['retained'],domain_eligible=row['domain_eligible']))
            target_counts[task]['two_component_input_labeled_points']+=1
            target_counts[task]['two_component_input_domain_filtered_labeled_points']+=bool(row['retained'] and row['domain_eligible'])
feature_schema=pa.schema([('dataset',pa.string()),('record_id',pa.string()),('source_row',pa.int64()),('feature_smiles',pa.string()),('solvent_smiles',pa.string()),('full_inchikey',pa.string()),('scaffold_group',pa.string()),('retained',pa.bool_()),('domain_eligible',pa.bool_()),('exclusion_reasons',pa.list_(pa.string())),('ecfp4_2048_packed',pa.binary()),('solvent_ecfp4_2048_packed',pa.binary()),('rdkit_2d',pa.list_(pa.float64())),('D_features',pa.list_(pa.float64())),('native_chromophore_D_features',pa.list_(pa.float64())),('solvent_rdkit_2d',pa.list_(pa.float64())),('input_ready',pa.bool_()),('original_fields_json',pa.string())])
label_schema=pa.schema([('dataset',pa.string()),('task',pa.string()),('record_id',pa.string()),('full_inchikey',pa.string()),('scaffold_group',pa.string()),('y',pa.float64()),('retained',pa.bool_()),('domain_eligible',pa.bool_())])
safe();pq.write_table(pa.Table.from_pylist(records,schema=feature_schema),out/'Joung2020.parquet',compression='zstd');pq.write_table(pa.Table.from_pylist(labels,schema=label_schema),out/'Joung2020_endpoint_rows.parquet',compression='zstd')
processable=[r for r in records if r['scaffold_group'] is not None]
fold_schema=pa.schema([('dataset',pa.string()),('repetition',pa.int32()),('fold',pa.int32()),('record_id',pa.string()),('scaffold_group',pa.string()),('split',pa.string()),('retained',pa.bool_()),('domain_eligible',pa.bool_())])
fold_path=out/'Joung2020_scaffold_folds.parquet';fold_counts=[];status='FIXED_FIVE_BY_FIVE_SCAFFOLD_FOLDS_CLOSED'
try:
    with pq.ParquetWriter(fold_path,fold_schema,compression='zstd') as writer:
        for repetition,fold,train,test in scaffold_folds([r['scaffold_group'] for r in processable]):
            fold_counts.append(dict(repetition=repetition,fold=fold,train_observations=len(train),test_observations=len(test)))
            output=[dict(dataset='Joung2020',repetition=repetition,fold=fold,record_id=processable[i]['record_id'],scaffold_group=processable[i]['scaffold_group'],split=split,retained=processable[i]['retained'],domain_eligible=processable[i]['domain_eligible']) for split,indices in (('train',train),('test',test)) for i in indices]
            safe();writer.write_table(pa.Table.from_pylist(output,schema=fold_schema))
except IncompleteComparison as error:status='UNRESOLVED_SCAFFOLD_PROTOCOL';counts['scaffold_protocol_error']=str(error)
spec=dict(dataset='Joung2020',status=status,features=str(out/'Joung2020.parquet'),official_endpoint_labels=str(out/'Joung2020_endpoint_rows.parquet'),scaffold_folds=str(fold_path),source_counts=dict(counts),endpoint_counts={k:dict(v) for k,v in target_counts.items()},fold_counts=fold_counts)
report=dict(status='JOUNG_ORIGINAL_CHROMOPHORE_SOLVENT_FEATURES_AND_FIXED_FOLDS_CLOSED',job=os.environ['SLURM_JOB_ID'],source_entry=str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),B0_source=str(source),full_inventory_scope_proof=str(proof_path),source_groups=[spec],counts=dict(counts),unresolved_source_solvent_lexemes=dict(unresolved_solvents),new_unit_tests=tests.countTestCases(),rdkit_version=rdBase.rdkitVersion,chromophore_and_solvent_component_descriptor_names=[name for name,_ in DESCRIPTORS],RF_input='Separate role-preserving Morgan r2/2048bit blocks for chromophore and solvent, concatenated 4096 total bits',LightGBM_input='Concatenated original chromophore and solvent RDKit2D descriptors',Chemprop_input='Official MulticomponentMPNN, ordered chromophore then solvent, default message passing/mean aggregation for each component and default FFN over concatenated embeddings',C1_D_input='Unchanged native 26 chromophore D values plus common explicit solvent RDKit2D context; context is an experimental condition, not a new geometry or P label',domain_policy='Original B0 chromophore flags unchanged; small solvent molecules are context conditions, not new domain-filtered target molecules',missing_input_policy='Unresolvable original solvent structures stay explicitly unavailable for all three baselines, without guessing solvents or changing original labels',fold_protocol='Five by five whole-chromophore Murcko-scaffold held out; all solvent observations stay together; all acyclic chromophores share one ACYCLIC scaffold',model_fits_run=False,task_screen_decisions_produced=False,new_solvent_conformers_generated=False,missing_native_D_filled=False,independent_numeric_readback=False)
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('JOUNG_TWO_COMPONENT_BINDING_CLOSED',json.dumps(report),flush=True)

PY
