#!/bin/bash
#SBATCH --job-name=ExpansionRx-official-source-binding
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/ExpansionRx_binding_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import csv,json,math,os,unittest
from pathlib import Path
from collections import Counter
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem,RDLogger
from workflows.benchmark_data.admission import protect
RDLogger.DisableLog('rdApp.error')
ENDPOINTS=('LogD','KSOL','HLM CLint','MLM CLint','Caco-2 Permeability Papp A>B','Caco-2 Permeability Efflux','MPPB','MBPB','MGMB')
def finite(value):
    try:result=float(value)
    except (TypeError,ValueError):return None
    return result if math.isfinite(result) else None
def original_key(smiles):
    mol=Chem.MolFromSmiles(smiles)
    if mol is None:raise ValueError('Original ExpansionRx structure cannot establish full molecular identity')
    key=Chem.MolToInchiKey(mol)
    if not key:raise ValueError('Original ExpansionRx graph lacks full molecular InChIKey')
    return key
def assert_identity(native,release):
    if native['Molecule Name']!=release['Molecule Name']:raise ValueError('Publisher molecule name mismatch')
    if original_key(native['SMILES'])!=original_key(release['SMILES']):raise ValueError('Publisher original full structure identity mismatch')
class IdentityTests(unittest.TestCase):
    def test_name_and_full_stereochemical_identity_are_both_required(self):
        assert_identity({'Molecule Name':'x','SMILES':'CCO'},{'Molecule Name':'x','SMILES':'OCC'})
        with self.assertRaises(ValueError):assert_identity({'Molecule Name':'x','SMILES':'CCO'},{'Molecule Name':'y','SMILES':'CCO'})
        with self.assertRaises(ValueError):assert_identity({'Molecule Name':'x','SMILES':'C[C@H](O)Cl'},{'Molecule Name':'x','SMILES':'C[C@@H](O)Cl'})
    def test_censored_or_missing_labels_are_not_silently_transformed(self):
        for value in ('>10','<1','nan','',None):self.assertIsNone(finite(value))
        self.assertEqual(finite('0'),0.)
tests=unittest.defaultTestLoader.loadTestsFromTestCase(IdentityTests)
if not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful():raise SystemExit(1)
entry=json.loads("{\"schema\":\"BENCHMARK_B0_AVAILABLE_DELIVERY_ENTRY_V1\",\"status\":\"D_AVAILABLE_PPRIME_RUNNING_S_P_PENDING\",\"authority\":\"docs/benchmark/USER_DIRECTIVE_20261118.md@07be7a0f04085398eeda2b7548afa46c668ffd9a\",\"data_root\":\"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119\",\"manifest\":\"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/delivery/job_4536591/manifest.json\",\"domain_counts_csv\":\"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/delivery/job_4536591/domain_counts.csv\",\"handoff_native_job\":4536591,\"handoff_native_state\":\"COMPLETED\",\"handoff_native_exit\":\"0:0\",\"source_groups\":11,\"domain_count_rows\":12,\"Pprime_current_job\":4536581,\"Pprime_current_node\":\"compute-0-12\",\"Pprime_current_workers\":8,\"Pprime_followup_jobs\":[4536588,4536590],\"Pprime_all_ready\":false,\"S_ready\":false,\"P_ready\":false,\"reference_quantum_status\":\"P pending with unrecovered S; Pprime defined on UFF only; dataset reference XYZ unchanged\",\"no_local_database_copies\":true,\"all_required_production_complete\":false,\"supplemental_sources\":{\"SAMPL6_7\":\"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/provenance/SAMPL6_7/job_4536607/manifest.json\",\"ExpansionRx_official_release\":\"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/raw/ExpansionRx_official_release/job_4536975/manifest.json\"},\"active_evaluation_scope\":{\"status\":\"B1_AND_LATER_SCOPE_EXCLUDES_FIVE_DEFERRED_ENDPOINTS\",\"decision_date\":\"2026-11-19\",\"endpoint_registry\":\"configs/benchmark_data/B1.deferred_tasks.json\",\"selector\":\"workflows.benchmark_data.task_selection.select_active_tasks\",\"strict_full_inventory_verification\":true,\"expected_deferred_endpoint_count\":5,\"effective_at\":\"B1_TASK_INVENTORY_BEFORE_MODEL_FITS\",\"b0_source_data_and_provenance\":\"UNALTERED\",\"failure_policy\":\"BLOCK_B1_UNTIL_ALL_FIVE_DEFERRED_IDENTIFIERS_MATCH\",\"scope_authority_commit\":\"fec1b994aa642ba8db74074134f909dcb4f165f0\",\"full_inventory_verification\":\"REQUIRED_BEFORE_B1_FITTING_NOT_PERFORMED_BY_B0\"},\"supplemental_source_policy\":{\"ExpansionRx_official_release\":\"Public ungated official post-challenge release pinned at 6b898ccc43d10d25b230fb09e22a6e30c30022b5; original nine endpoints and B0 train/test membership are unchanged; validate original Molecule Name and full original structure identity before using finite TEST labels, retain original TRAIN labels; no raw-only RLM endpoint\"}}")
root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,64*1024**2,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'ExpansionRx_release_binding'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
runtime_entry=out/'B0.DELIVERY.json';runtime_entry.write_text(json.dumps(entry,indent=2)+'\n')
# Read the immutable runtime rendering of the published uniform B0 entry.
entry=json.loads(runtime_entry.read_text());release_manifest=Path(entry['supplemental_sources']['ExpansionRx_official_release'])
release=json.loads(release_manifest.read_text())
assert release['publisher_gated'] is False
assert release['publisher_revision']=='6b898ccc43d10d25b230fb09e22a6e30c30022b5'
files={record['filename']:Path(record['path']) for record in release['files']}
released={}
for split in ('train','test'):
    with files['expansion_data_'+split+'.csv'].open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if set(reader.fieldnames)!=set(('Molecule Name','SMILES')+ENDPOINTS):raise ValueError('Official release endpoint schema changed')
        records=list(reader)
    mapping={r['Molecule Name']:r for r in records}
    if len(mapping)!=len(records):raise ValueError('Ambiguous publisher molecule IDs')
    released[split]=mapping
proof_path=b1/'endpoint_catalog/job_4536889/manifest.json';proof=json.loads(proof_path.read_text())
assert proof['deferred_registry_full_inventory_verified'] and proof['deferred_endpoint_count']==5 and proof['candidate_counts_by_source_group']['ExpansionRx']==9
manifest=json.loads(Path(entry['manifest']).read_text());source=Path(manifest['source_groups']['ExpansionRx']['records'])
schema=pa.schema([('dataset',pa.string()),('task',pa.string()),('record_id',pa.string()),('source_row',pa.int64()),('official_molecule_name',pa.string()),('original_full_inchikey',pa.string()),('official_split',pa.string()),('y',pa.float64()),('label_source',pa.string()),('retained',pa.bool_()),('domain_eligible',pa.bool_()),('blind_fallback_required',pa.bool_())])
counts=Counter();coverage={e:Counter() for e in ENDPOINTS};seen={'train':set(),'test':set()}
with pq.ParquetWriter(out/'ExpansionRx_official_endpoint_rows.parquet',schema,compression='zstd') as writer:
    for batch in pq.ParquetFile(source).iter_batches(batch_size=256):
        buffer=[]
        for row in batch.to_pylist():
            native=json.loads(row['original_fields_json']);name=native['Molecule Name']
            split=str(row['official_split']).lower()
            if split not in released:raise ValueError('B0 original official split is not bound')
            if name in seen[split]:raise ValueError('Duplicate B0 original publisher ID')
            seen[split].add(name)
            publisher=released[split][name];assert_identity(native,publisher);key=original_key(native['SMILES'])
            counts[split+'_identity_bound_molecules']+=1
            for endpoint in ENDPOINTS:
                y=finite(native.get(endpoint)) if split=='train' else finite(publisher.get(endpoint))
                if split=='train' and finite(native.get(endpoint))!=finite(publisher.get(endpoint)):counts['original_TRAIN_labels_differ_from_current_release_'+endpoint]+=1
                if y is None:coverage[endpoint][split+'_missing_original_or_public_label']+=1;continue
                coverage[endpoint][split+'_finite_label_points']+=1
                coverage[endpoint][split+('_retained_points' if row['retained'] and row['domain_eligible'] else '_excluded_points')]+=1
                buffer.append(dict(dataset='ExpansionRx',task=endpoint,record_id=row['record_id'],source_row=row['source_row'],official_molecule_name=name,original_full_inchikey=key,official_split=split,y=y,label_source='original_B0_TRAIN' if split=='train' else 'official_public_post_challenge_TEST',retained=row['retained'],domain_eligible=row['domain_eligible'],blind_fallback_required=row['blind_fallback_required']))
        safe()
        if buffer:writer.write_table(pa.Table.from_pylist(buffer,schema=schema))
for split in ('train','test'):
    if seen[split]!=set(released[split]):raise ValueError('Official release and B0 original split membership differ')
report=dict(status='EXPANSIONRX_ORIGINAL_NINE_ENDPOINTS_PUBLIC_TEST_LABELS_BOUND',job=os.environ['SLURM_JOB_ID'],source_entry=str(runtime_entry),source_entry_GitHub='configs/benchmark_data/B0.DELIVERY.json@benchmark-b1-20261119',original_B0_manifest=entry['manifest'],source_release_manifest=str(release_manifest),source_release_revision=release['publisher_revision'],license=release['license'],original_domain_records=str(source),scope_proof=str(proof_path),official_endpoint_labels=str(out/'ExpansionRx_official_endpoint_rows.parquet'),counts=dict(counts),endpoint_coverage={k:dict(v) for k,v in coverage.items()},new_unit_tests=tests.countTestCases(),original_TRAIN_labels_retained=True,original_official_split_unchanged=True,original_full_inchikey_identity_join=True,TEST_domain_filter_applied=False,domain_outside_TEST_policy='Fit-population TRAIN mean, without TEST removal',endpoint_units_and_values='Original publisher units and finite ML-ready values; no logs, normalization or censored-value substitution during binding',raw_only_RLM_endpoint_added=False,model_fits_run=False,task_screen_decisions_produced=False,independent_numeric_readback=False)
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('EXPANSIONRX_RELEASE_BINDING_CLOSED',json.dumps(report),flush=True)

PY
