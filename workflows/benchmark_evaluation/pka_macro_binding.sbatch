#!/bin/bash
#SBATCH --job-name=B1-pKa-macro-label-binding
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=01:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_pKa_macro_%j.log
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
from collections import defaultdict,Counter
from rdkit import Chem
import pyarrow as pa
import pyarrow.parquet as pq
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.pkahub_annotations import transition
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
def safe():protect(root,128*1024**2,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'pKa_macro'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
proof=json.loads((b1/'endpoint_catalog/job_4536889/manifest.json').read_text());assert proof['deferred_registry_full_inventory_verified']
manifest=json.loads(Path(entry['manifest']).read_text())
supplemental_path=entry.get('supplemental_sources',{}).get('SAMPL6_7') or manifest.get('supplemental_sources',{}).get('SAMPL6_7')
if isinstance(supplemental_path,dict):supplemental_path=supplemental_path.get('manifest')
sampl_manifest=json.loads(Path(supplemental_path).read_text())
blind_rows=pq.read_table(sampl_manifest['records']).to_pylist()
blind_keys=set();blind_source_keys=set();unresolved_blind=[];external=defaultdict(list);external_coverage=Counter()
for row in blind_rows:
    challenge=row['source_challenge'];raw=json.loads(row['original_fields_json'])
    assert challenge in ('SAMPL6','SAMPL7')
    source_key=(challenge,str(row['rawdataID'] or ''));blind_source_keys.add(source_key)
    key=str(row.get('original_InChIKey') or '').strip()
    if not KEY.fullmatch(key):key=full_key(raw,row.get('original_smiles'))
    if not key:
        unresolved_blind.append({'challenge':challenge,'rawdataID':row['rawdataID'],'reason':'FULL_INCHIKEY_UNRESOLVED'});continue
    blind_keys.add(key)
    links=json.loads(row['unified_links_json']);usable=[link for link in links if not link['author_excluded'] and link['domain_record_id']]
    y=finite(row['original_pKa_lexeme']);step=transition(raw.get('assigned_charge_state_transition'));endpoint=endpoint_from_transition(step)
    if y is None or endpoint is None or not usable:
        external_coverage['unusable_original_label_transition_or_curated_domain_link']+=1
        unresolved_blind.append({'challenge':challenge,'rawdataID':row['rawdataID'],'full_inchikey':key,'reason':'ORIGINAL_LABEL_OR_TRANSITION_OR_CURATED_B0_LINK_UNAVAILABLE','usable_links':len(usable)});continue
    link=sorted(usable,key=lambda x:x['domain_record_id'])[0]
    external[(challenge,key,endpoint)].append({'endpoint':endpoint,'full_inchikey':key,'record_id':link['domain_record_id'],'model_smiles':link['domain_model_smiles'],'y':y,'source_dataset':challenge,'rawdataID':str(row['rawdataID'] or ''),'challenge_compound_id':row.get('challenge_compound_id'),'transition_from':step[0],'transition_to':step[1],'fit_role':'EXTERNAL_TEST','challenge':challenge})
    external_coverage['usable_original_rows']+=1
if any(row['reason']=='FULL_INCHIKEY_UNRESOLVED' for row in unresolved_blind):
    # All blind molecules must be known before any TRAIN list can be frozen.
    report={'status':'UNRESOLVED_BLIND_IDENTITY_TRAINING_NOT_FROZEN','job':os.environ['SLURM_JOB_ID'],'unresolved_blind':unresolved_blind,'model_fits_run':False}
    safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('PKA_MACRO_BINDING_UNRESOLVED',out/'manifest.json',flush=True);raise SystemExit(0)
training=defaultdict(list);exclusions=[];counts=Counter();transitions_by_key=defaultdict(set)
for batch in pq.ParquetFile(manifest['source_groups']['pKahub']['records']).iter_batches(batch_size=2048):
    for row in batch.to_pylist():
        counts['curated_macro_source_rows']+=1;raw=json.loads(row['original_fields_json'])
        key=full_key(raw,row['original_smiles']);source_dataset=str(raw.get('dataset') or '').strip();rawid=str(raw.get('rawdataID') or '').strip()
        if key is None:counts['unresolved_full_identity']+=1;continue
        step=transition(raw.get('assigned_charge_state_transition'));endpoint=endpoint_from_transition(step);y=finite(raw.get('Exp_Macro_pKa_processed'))
        if y is not None and step is not None:transitions_by_key[key].add(step)
        if key in blind_keys or (source_dataset,rawid) in blind_source_keys:
            exclusions.append({'record_id':row['record_id'],'full_inchikey':key,'source_dataset':source_dataset,'rawdataID':rawid,'reason':'FULL_INCHIKEY_OVERLAP_WITH_SAMPL6_OR_SAMPL7' if key in blind_keys else 'EXPLICIT_DATASET_RAWDATAID_BLIND_SOURCE_KEY'})
            counts['TRAIN_excluded_blind_overlap_rows']+=1;continue
        if not (row['retained'] and row['domain_eligible']):counts['outside_domain_rows']+=1;continue
        if y is None or endpoint is None:counts['unparsed_label_or_transition_rows']+=1;continue
        training[(key,endpoint)].append({'endpoint':endpoint,'full_inchikey':key,'record_id':row['record_id'],'model_smiles':row['model_smiles'],'y':y,'source_dataset':source_dataset,'rawdataID':rawid,'challenge_compound_id':None,'transition_from':step[0],'transition_to':step[1],'fit_role':'TRAIN','challenge':None})
selected=[]
for (_,endpoint),rows in sorted(training.items()):selected.append(choose_strongest(rows,endpoint))
for (challenge,key,endpoint),rows in sorted(external.items()):selected.append(choose_strongest(rows,endpoint))
safe()
schema=pa.schema([('endpoint',pa.string()),('full_inchikey',pa.string()),('record_id',pa.string()),('model_smiles',pa.string()),('y',pa.float64()),('source_dataset',pa.string()),('rawdataID',pa.string()),('challenge_compound_id',pa.string()),('transition_from',pa.int32()),('transition_to',pa.int32()),('fit_role',pa.string()),('challenge',pa.string())])
target=out/'macro_endpoint_rows.parquet';pq.write_table(pa.Table.from_pylist(selected,schema=schema),target,compression='zstd')
with (out/'TRAIN_blind_overlap_exclusions.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=['record_id','full_inchikey','source_dataset','rawdataID','reason']);writer.writeheader();writer.writerows(exclusions)
populations=Counter((row['endpoint'],row['fit_role'],row['challenge']) for row in selected)
report={'status':'MACRO_ENDPOINT_BINDING_FROZEN_BEFORE_FITS','job':os.environ['SLURM_JOB_ID'],'unit_tests':tests.countTestCases(),'source_entry':str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),'B0_domain_source':manifest['source_groups']['pKahub']['records'],'SAMPL_source_manifest':str(supplemental_path),'source_join_key':['dataset','rawdataID'],'external_compound_key':['challenge','challenge_compound_id'],'records':str(target),'TRAIN_exclusions':str(out/'TRAIN_blind_overlap_exclusions.csv'),'counts':dict(counts),'populations':[{'endpoint':key[0],'fit_role':key[1],'challenge':key[2],'molecules':value} for key,value in sorted(populations.items(),key=lambda x:tuple(str(v) for v in x[0]))],'blind_unique_full_inchikeys':len(blind_keys),'external_unusable_rows':unresolved_blind,'external_coverage':dict(external_coverage),'label_definition':'Published unit-deprotonation macro transitions: start charge <=0 acidic, start charge >0 basic. Per complete original molecular InChIKey retain the lowest original acid pKa and highest original base pKa; ties by original dataset/rawdataID/record_id. No inferred or averaged new experimental values.','transition_semantics_source':'https://pubs.acs.org/doi/10.1021/acs.jcim.6c00107','multiple_observed_macro_transition_molecules':sum(len(value)>1 for value in transitions_by_key.values()),'multiple_macro_transitions_are_not_site_counts':True,'experimental_micro_records':0,'single_ionization_site_molecules':None,'single_site_atom_task':'UNRESOLVED_SOURCE_EXPORTS_DO_NOT_ANNOTATE_EXPERIMENTAL_ATOM_SITES; do not equate a single observed macro transition with a single ionization site','model_fits_run':False,'B1_screen_decisions_produced':False,'predicted_microspecies_used_as_experimental_labels':False,'independent_numeric_readback':False}
safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('PKA_MACRO_BINDING_CLOSED',out/'manifest.json','populations',json.dumps(report['populations']),'excluded_overlap_rows',len(exclusions),flush=True)

PY
