#!/bin/bash
#SBATCH --job-name=B1-active-endpoint-catalog
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --cpus-per-task=2
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=01:00:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/B1_endpoint_catalog_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import csv,json,math,os,unittest
from collections import Counter
from pathlib import Path
import pyarrow.parquet as pq
from workflows.benchmark_data.admission import protect
from workflows.benchmark_data.task_selection import select_active_tasks,canonical_task_key
EXP=('LogD','KSOL','HLM CLint','MLM CLint','Caco-2 Permeability Papp A>B','Caco-2 Permeability Efflux','MPPB','MBPB','MGMB')
BIO=('LOG_HLM_CLint','LOG_RLM_CLint','LOG_MDR1-MDCK_ER','LOG_HPPB','LOG_RPPB','LOG_SOLUBILITY')
OPT=('Absorption max (nm)','Emission max (nm)','Lifetime (ns)','Quantum yield','log(e/mol-1 dm3 cm-1)','abs FWHM (cm-1)','emi FWHM (cm-1)','abs FWHM (nm)','emi FWHM (nm)')
def specs(group,source):
    level='molecule'
    if group=='ExpansionRx':columns=EXP;policy='OFFICIAL_TRAIN_TEST';binding='RAW_SCALAR'
    elif group=='MoleculeACE':columns=('y',);policy='OFFICIAL_TRAIN_TEST';binding='RAW_SCALAR'
    elif group=='PharmaBench':columns=('value',);policy='OFFICIAL_SCAFFOLD_TRAIN_TEST';binding='RAW_SCALAR'
    elif group=='TDC_ADMET':columns=('Y',);policy='OFFICIAL_TRAIN_VAL_TEST';binding='RAW_SCALAR_TASKTYPE_METADATA_PENDING'
    elif group=='Biogen_ADME':columns=BIO;policy='OFFICIAL_POLARIS_ENDPOINT_MASK_JOIN_REQUIRED';binding='RAW_SCALAR'
    elif group=='ASAP_Polaris2025':columns=('HLM','MLM','KSOL','LogD','MDR1-MDCKII');policy='OFFICIAL_SET_PLUS_PUBLISHED_CLINT_EXCLUSIONS';binding='RAW_SCALAR'
    elif group=='Joung2020':columns=OPT;policy='FIVE_BY_FIVE_SCAFFOLD_CHROMOPHORE_CV';binding='RAW_SCALAR_SOLVENT_FEATURE_BINDING_REQUIRED'
    elif group=='pKahub':columns=('macro_acid','macro_base','single_site_mechanism');policy='SAMPL6_7_FULL_INCHIKEY_BLIND_EXCLUSION_AND_SCAFFOLD_CV';binding='MACRO_AGGREGATION_OR_CONFIRMED_SINGLE_SITE_BINDING_REQUIRED'
    elif group=='C7H10O2':columns=('G4MP2_absolute','G4MP2_minus_B3LYP');policy='FIVE_BY_FIVE_SCAFFOLD_CV';binding='B0_C7_TARGET_OVERLAY_JOIN_REQUIRED'
    elif group=='PPE1694':columns=('delta_Hf_minus_group_additivity','delta_Hf_minus_semiempirical');policy='FIVE_BY_FIVE_SCAFFOLD_CV';binding='PPE_RESIDUAL_AND_GROUP_ADDITIVITY_BASELINE_BINDING_REQUIRED'
    elif group=='NMRShiftDB2':
        nucleus_file=canonical_task_key(group,source).split('::',1)[1]
        if nucleus_file not in ('carbon.parquet','hydrogen.parquet'):raise ValueError('Unknown NMR nucleus source')
        columns=('13C',) if nucleus_file=='carbon.parquet' else ('1H',)
        policy='ORIGINAL_NMRSHIFTDB2_2018_RELEASE_TRAIN_TEST';binding='FULL_ORIGINAL_STANDARD_ATOM_LABEL_BINDING_REQUIRED';level='atom'
    else:raise ValueError('Unknown source group')
    base=canonical_task_key(group,source) if group not in ('ExpansionRx','C7H10O2','PPE1694','pKahub','NMRShiftDB2') else group.casefold()
    return [{'endpoint_key':base+'::'+column,'target':column,'level':('atom' if column=='single_site_mechanism' else level),'split_policy':policy,'binding':binding} for column in columns]
def scalar(value):
    if value is None or str(value).strip() in ('','nan','NaN','NA','N/A','-'):return 'MISSING',None
    try:number=float(value)
    except (TypeError,ValueError):return 'UNPARSED',None
    return ('FINITE',number) if math.isfinite(number) else ('MISSING',None)
def split_kind(value):
    token=str(value or '').strip().casefold()
    if token in ('train','train_val','train_df'):return 'TRAIN'
    if token in ('test','test_blinded','test_df'):return 'TEST'
    return 'UNBOUND'
class CatalogTests(unittest.TestCase):
    def test_no_descriptor_or_identity_column_as_optical_label(self):
        columns=[x['target'] for x in specs('Joung2020','source.csv')]
        self.assertEqual(len(columns),9)
        self.assertNotIn('Molecular weight (g mol-1)',columns)
        self.assertNotIn('Chromophore',columns)
    def test_official_tdc_source_paths_collapse(self):
        self.assertEqual(specs('TDC_ADMET','admet_group/example/train_val.csv')[0]['endpoint_key'],specs('TDC_ADMET','admet_group/example/test.csv')[0]['endpoint_key'])
    def test_mechanism_not_fabricated_from_macro(self):
        rows=specs('pKahub','combined_unified_dataset.tsv')
        self.assertEqual([r['level'] for r in rows],['molecule','molecule','atom'])
        self.assertTrue(all('BINDING_REQUIRED' in r['binding'] for r in rows))
    def test_missing_and_multivalued_labels_are_distinct(self):
        self.assertEqual(scalar('1.2;1.4')[0],'UNPARSED')
        self.assertEqual(scalar('nan')[0],'MISSING')
        self.assertEqual(scalar('1.2'),('FINITE',1.2))
    def test_blind_test_split_stays_test(self):
        self.assertEqual(split_kind('test_blinded'),'TEST')
        self.assertEqual(split_kind('train_val'),'TRAIN')
    def test_official_expansion_split_files_are_one_endpoint(self):
        self.assertEqual([r['endpoint_key'] for r in specs('ExpansionRx','train.csv')],[r['endpoint_key'] for r in specs('ExpansionRx','test_blinded.csv')])
    def test_nmr_nuclei_remain_separate_for_full_paths(self):
        self.assertEqual(specs('NMRShiftDB2','reference/carbon.parquet')[0]['target'],'13C')
        self.assertEqual(specs('NMRShiftDB2','reference/hydrogen.parquet')[0]['target'],'1H')
        with self.assertRaises(ValueError):specs('NMRShiftDB2','unknown.parquet')
    def test_unknown_group_fails(self):
        with self.assertRaises(ValueError):specs('unknown','file')
suite=unittest.defaultTestLoader.loadTestsFromTestCase(CatalogTests)
if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():raise SystemExit(1)
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text())
root=Path(entry['data_root']);quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,128*1024**2,quota,own_concurrent_bytes=24*1024**3)
safe()
manifest=json.loads(Path(entry['manifest']).read_text())
inventory=set();aggregates={};membership={}
for group,spec in manifest['source_groups'].items():
    paths=[spec['records']] if spec.get('records') else list(spec['records_by_nucleus'].values())
    for path in paths:
        for batch in pq.ParquetFile(path).iter_batches(batch_size=2048,columns=['source_file','original_fields_json','official_split','retained','domain_eligible','blind_fallback_required']):
            for source_row in batch.to_pylist():
                source=source_row['source_file'];pair=(group,source);inventory.add(pair)
                raw=json.loads(source_row['original_fields_json'])
                for definition in specs(group,source):
                    key=definition['endpoint_key'];membership.setdefault(key,set()).add(pair)
                    row=aggregates.setdefault(key,dict(definition,dataset=group,n_source_rows=0,n_retained_rows=0,n_domain_eligible_rows=0,n_blind_fallback_rows=0,n_finite_raw_labels=0,n_missing_raw_labels=0,n_unparsed_raw_labels=0,n_train_raw_labels=0,n_test_raw_labels=0,n_unbound_split_raw_labels=0))
                    row['n_source_rows']+=1;row['n_retained_rows']+=int(source_row['retained']);row['n_domain_eligible_rows']+=int(source_row['domain_eligible']);row['n_blind_fallback_rows']+=int(source_row['blind_fallback_required'])
                    if not row['binding'].startswith('RAW_SCALAR'):continue
                    state,_=scalar(raw.get(row['target']))
                    row[{'FINITE':'n_finite_raw_labels','MISSING':'n_missing_raw_labels','UNPARSED':'n_unparsed_raw_labels'}[state]]+=1
                    if state=='FINITE':
                        kind=split_kind(source_row['official_split'])
                        row[{'TRAIN':'n_train_raw_labels','TEST':'n_test_raw_labels','UNBOUND':'n_unbound_split_raw_labels'}[kind]]+=1
            safe()
active=set(select_active_tasks(sorted(inventory),verify_full_inventory=True))
rows=[]
for key,row in sorted(aggregates.items()):
    source_pairs=membership[key]
    if not source_pairs & active:continue
    if not source_pairs <= active:raise ValueError('Endpoint mixes active and deferred original tasks')
    row['status']='CANDIDATE_ONLY_NOT_SCREENED'
    if row['binding'].startswith('RAW_SCALAR') and row['split_policy'].startswith('OFFICIAL') and row['n_test_raw_labels']==0:row['status']='MISSING_TEST_LABELS_OR_OFFICIAL_SPLIT_JOIN'
    rows.append(row)
safe()
out=root.parent/('benchmark_B1_20261119/endpoint_catalog/job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
with (out/'candidate_endpoints.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
report={'status':'ACTIVE_CANDIDATE_ENDPOINT_CATALOG_PRODUCED_NO_FITS','job':os.environ['SLURM_JOB_ID'],'new_logic_unit_tests':suite.countTestCases(),'supersedes_catalog_job':4536886,'producer_correction':'Unify official train/test source files into the same ExpansionRx endpoint; classify NMR nuclei by canonical source basename rather than full-path equality','deferred_registry_full_inventory_verified':True,'deferred_endpoint_count':5,'candidate_endpoint_count':len(rows),'candidate_counts_by_source_group':dict(Counter(r['dataset'] for r in rows)),'source_entry':str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),'source_manifest':entry['manifest'],'catalog':str(out/'candidate_endpoints.csv'),'scope':'All eleven B0 candidate source groups; NMR full-original-source binding remains required; raw label counts are not final evaluated point counts','final_task_roster':False,'B1_task_screen_decisions_produced':False,'no_database_copies':True}
(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
PY
