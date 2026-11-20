#!/bin/bash
#SBATCH --job-name=B1-pKa-2D-full-source-features
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=04:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_pKa_features_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import csv,json,math,os,re,unittest
from pathlib import Path
from collections import Counter,defaultdict
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem,DataStructs,rdBase,RDLogger
from rdkit.Chem import Descriptors,rdFingerprintGenerator
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.pkahub_annotations import transition
RDLogger.DisableLog('rdApp.error')
KEY=re.compile(r'^[A-Z]{14}-[A-Z]{10}-[A-Z]$')
def full_key(raw,fallback_smiles=None):
    key=str(raw.get('InChIKey') or '').strip()
    if KEY.fullmatch(key):return key
    smiles=raw.get('reprSMILES_processed') or fallback_smiles
    mol=Chem.MolFromSmiles(smiles) if smiles else None
    key=Chem.MolToInchiKey(mol) if mol is not None else ''
    return key if KEY.fullmatch(key) else None
def endpoint_from_transition(step):
    if step is None or step[0]-step[1]!=1:return None
    return 'acid' if step[0]<=0 else 'base'
def choose_strongest(rows,endpoint):
    if endpoint not in ('acid','base'):raise ValueError('Unknown macro endpoint')
    direction=1 if endpoint=='acid' else -1
    return min(rows,key=lambda r:(direction*r['y'],r['source_dataset'],r['rawdataID'],r['record_id']))
def finite(value):
    try:value=float(value)
    except (ValueError,TypeError):return None
    return value if math.isfinite(value) else None
class MacroTests(unittest.TestCase):
    def test_transition_direction_and_class_are_not_micro_sites(self):
        self.assertEqual(endpoint_from_transition(transition('0 >> -1')),'acid')
        self.assertEqual(endpoint_from_transition(transition('1 >> 0')),'base')
        self.assertIsNone(endpoint_from_transition(transition('1 >> -1')))
    def test_strongest_acid_and_base_keep_original_experimental_values(self):
        rows=[dict(y=x,source_dataset='example',rawdataID=str(x),record_id=str(x)) for x in (4.,7.,10.)]
        self.assertEqual(choose_strongest(rows,'acid')['y'],4.)
        self.assertEqual(choose_strongest(rows,'base')['y'],10.)
    def test_full_stereo_key_is_not_connectivity_prefix(self):
        a=full_key({},'C[C@H](O)Cl');b=full_key({},'C[C@@H](O)Cl')
        self.assertEqual(a.split('-')[0],b.split('-')[0]);self.assertNotEqual(a,b)
    def test_challenge_compound_ids_remain_namespaced(self):
        self.assertNotEqual(('SAMPL6','SM01'),('SAMPL7','SM01'))
    def test_ties_are_order_independent(self):
        rows=[dict(y=4.,source_dataset=d,rawdataID='one',record_id=d) for d in ('B','A')]
        self.assertEqual(choose_strongest(rows,'acid'),choose_strongest(rows[::-1],'acid'))
    def test_censored_macro_labels_are_not_filled(self):
        self.assertIsNone(finite('<4'));self.assertIsNone(finite('nan'))
tests=unittest.defaultTestLoader.loadTestsFromTestCase(MacroTests)
if not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,2*1024**3,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'B1_pKa_features'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
proof_path=b1/'endpoint_catalog/job_4536889/manifest.json';proof=json.loads(proof_path.read_text());assert proof['deferred_registry_full_inventory_verified'] and proof['deferred_endpoint_count']==5
manifest=json.loads(Path(entry['manifest']).read_text())
canonical_path=b1/'pKa_macro/job_4536926/manifest.json';canonical=json.loads(canonical_path.read_text())
selected=pq.read_table(canonical['records']).to_pylist()
primary_keys={(r['full_inchikey'],r['endpoint']) for r in selected if r['fit_role']=='TRAIN'}
sampl_manifest=json.loads(Path(entry['supplemental_sources']['SAMPL6_7']).read_text())
blind_keys=set();blind_source_keys=set()
for row in pq.read_table(sampl_manifest['records']).to_pylist():
    raw=json.loads(row['original_fields_json']);key=row.get('original_InChIKey') or full_key(raw,row.get('original_smiles'))
    if not key or not KEY.fullmatch(key):raise ValueError('Unresolved complete external blind identity')
    blind_keys.add(key);blind_source_keys.add((row['source_challenge'],str(row['rawdataID'] or '')))
outside=defaultdict(list);sources={};counts=Counter()
for batch in pq.ParquetFile(manifest['source_groups']['pKahub']['records']).iter_batches(batch_size=2048):
    for row in batch.to_pylist():
        sources[row['record_id']]=row
        if row['retained'] and row['domain_eligible']:continue
        raw=json.loads(row['original_fields_json']);key=full_key(raw,row['original_smiles'])
        source_dataset=str(raw.get('dataset') or '').strip();rawid=str(raw.get('rawdataID') or '').strip()
        if key is None:counts['outside_full_original_identity_unresolved']+=1;continue
        if key in blind_keys or (source_dataset,rawid) in blind_source_keys:counts['outside_blind_overlap_excluded']+=1;continue
        step=transition(raw.get('assigned_charge_state_transition'));endpoint=endpoint_from_transition(step);y=finite(raw.get('Exp_Macro_pKa_processed'))
        if y is None or endpoint is None:counts['outside_label_or_transition_unparsed']+=1;continue
        if (key,endpoint) in primary_keys:
            # Keep the frozen primary source label unchanged in both fits.
            counts['outside_source_rows_for_existing_frozen_primary_endpoint']+=1;continue
        outside[(key,endpoint)].append(dict(endpoint=endpoint,full_inchikey=key,record_id=row['record_id'],model_smiles=row['model_smiles'] or row['original_smiles'],y=y,source_dataset=source_dataset,rawdataID=rawid,challenge_compound_id=None,transition_from=step[0],transition_to=step[1],fit_role='TRAIN',challenge=None))
outside_selected=[choose_strongest(rows,endpoint) for (key,endpoint),rows in sorted(outside.items())]
selected.extend(outside_selected)
generator=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=False)
descriptors=list(Descriptors._descList);cache={}
for job,groups in ((4536908,('MoleculeACE','PharmaBench')),(4536920,('TDC_ADMET','ASAP_Polaris2025','Biogen_ADME','ExpansionRx','Joung2020'))):
    for group in groups:
        path=b1/('B1_molecular_features/job_'+str(job))/(group+'.parquet')
        for batch in pq.ParquetFile(path).iter_batches(batch_size=2048,columns=['feature_smiles','ecfp4_2048_packed','rdkit_2d']):
            for row in batch.to_pylist():cache[row['feature_smiles']]=(row['ecfp4_2048_packed'],row['rdkit_2d'])
def featurize(smiles):
    mol=Chem.MolFromSmiles(smiles) if smiles else None
    if mol is None:return None,None
    values=[]
    for name,function in descriptors:
        try:value=float(function(mol))
        except Exception:value=float('nan')
        values.append(value if math.isfinite(value) else float('nan'))
    return DataStructs.BitVectToBinaryText(generator.GetFingerprint(mol)),values
schema=pa.schema([('dataset',pa.string()),('task',pa.string()),('record_id',pa.string()),('original_record_id',pa.string()),('source_dataset',pa.string()),('rawdataID',pa.string()),('challenge',pa.string()),('full_inchikey',pa.string()),('feature_smiles',pa.string()),('official_split',pa.string()),('y',pa.float64()),('retained',pa.bool_()),('domain_eligible',pa.bool_()),('exclusion_reasons',pa.list_(pa.string())),('ecfp4_2048_packed',pa.binary()),('rdkit_2d',pa.list_(pa.float64())),('feature_state',pa.string()),('frozen_primary_label',pa.bool_())])
task_counts=defaultdict(Counter);outside_ids={r['record_id'] for r in outside_selected}
with pq.ParquetWriter(out/'pKahub.parquet',schema,compression='zstd') as writer:
    buffer=[]
    for label in selected:
        native=sources[label['record_id']]
        smiles=label['model_smiles'] or native['model_smiles'] or native['original_smiles']
        if smiles not in cache:cache[smiles]=featurize(smiles)
        fp,rdkit2d=cache[smiles];state='FEATURES_READY' if fp is not None else 'UNPARSEABLE_GRAPH'
        split='train' if label['fit_role']=='TRAIN' else 'test'
        task='macro_'+label['endpoint'];retained=bool(native['retained']);domain=bool(native['domain_eligible'])
        evaluation_id=label['record_id'] if split=='train' else label['challenge']+':'+label['record_id']
        record=dict(dataset='pKahub',task=task,record_id=evaluation_id,original_record_id=label['record_id'],source_dataset=label['source_dataset'],rawdataID=label['rawdataID'],challenge=label['challenge'],full_inchikey=label['full_inchikey'],feature_smiles=smiles,official_split=split,y=label['y'],retained=retained,domain_eligible=domain,exclusion_reasons=native['exclusion_reasons'],ecfp4_2048_packed=fp,rdkit_2d=rdkit2d,feature_state=state,frozen_primary_label=label['record_id'] not in outside_ids)
        buffer.append(record);task_counts[task][split+'_source_rows']+=1;task_counts[task][split+('_retained_points' if retained and domain else '_excluded_points')]+=1;task_counts[task][state]+=1
        if len(buffer)>=256:
            safe();writer.write_table(pa.Table.from_pylist(buffer,schema=schema));buffer.clear()
    if buffer:safe();writer.write_table(pa.Table.from_pylist(buffer,schema=schema))
report=dict(status='PKA_FROZEN_MACRO_PRIMARY_PLUS_OUTSIDE_DOMAIN_FULL_DIAGNOSTIC_FEATURES_CLOSED',job=os.environ['SLURM_JOB_ID'],source_entry=str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),source_manifest=entry['manifest'],scope_proof=str(proof_path),frozen_primary_label_binding=str(canonical_path),SAMPL_source_manifest=entry['supplemental_sources']['SAMPL6_7'],records=str(out/'pKahub.parquet'),outside_source_binding_counts=dict(counts),outside_additional_TRAIN_macro_points=len(outside_selected),task_counts={k:dict(v) for k,v in task_counts.items()},rdkit_version=rdBase.rdkitVersion,rdkit_2d_names=[name for name,_ in descriptors],ecfp4=dict(radius=2,bits=2048,include_chirality=False),native_missing_values_not_filled=True,original_full_inchikey_used_for_blind_exclusion=True,frozen_primary_labels_modified=False,outside_TRAIN_diagnostic='Add strongest original macro values only for outside-domain complete identities absent from frozen primary; never replace a frozen primary label',TEST_challenges_namespaced=True,model_fits_run=False,task_screen_decisions_produced=False,single_site_mechanism='UNRESOLVED_SOURCE_HAS_NO_UNIQUE_EXPERIMENTAL_ATOM_SITE_ANNOTATIONS',new_unit_tests=tests.countTestCases(),independent_numeric_readback=False)
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('PKA_B1_FEATURES_CLOSED',json.dumps(report),flush=True)

PY
