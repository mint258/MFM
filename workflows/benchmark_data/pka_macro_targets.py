"""Prepare macro acid/base targets and exact full-InChIKey SAMPL exclusions."""
import argparse
from collections import Counter,defaultdict
import json
import math
from pathlib import Path
import re
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem
from .pkahub_annotations import transition
from .pprime_tmpfs_queue import capacity

KEY=re.compile(r'^[A-Z]{14}-[A-Z]{10}-[A-Z]$')

def full_key(smiles,declared=None):
    if declared and KEY.fullmatch(declared.strip()):return declared.strip()
    mol=Chem.MolFromSmiles(smiles)
    if mol is None:raise ValueError('Cannot establish complete blind/training InChIKey')
    key=Chem.MolToInchiKey(mol)
    if not KEY.fullmatch(key):raise ValueError('Complete InChIKey unavailable')
    return key

def endpoint(step):
    if step is None or step[0]-step[1]!=1:return None
    return 'base' if step[0]>0 else 'acid'

def strongest(rows):
    grouped=defaultdict(list)
    for row in rows:
        step=transition(row['transition'])
        if endpoint(step) is not None and math.isfinite(row['value']):grouped[step].append(row)
    candidates=defaultdict(list)
    for step,values in grouped.items():
        mean=math.fsum(v['value'] for v in values)/len(values)
        candidates[endpoint(step)].append((mean,step,values))
    result={}
    for kind,values in candidates.items():
        chosen=(min(values,key=lambda v:(v[0],v[1])) if kind=='acid'
                else min(values,key=lambda v:(-v[0],v[1])))
        result[kind]=chosen
    return result

def targets_for_group(rows,role,group_key,challenge=None,compound=None):
    result=[]
    for kind,(value,step,measurements) in strongest(rows).items():
        anchor=min(measurements,key=lambda r:r['source_row'])
        result.append(dict(record_id=role+':'+group_key+':'+kind,endpoint='macro_pKa_'+kind,
            target_value=value,target_units='pKa',benchmark_role=role,
            full_InChIKey=anchor['full_InChIKey'],source_molids=sorted({r['molid'] for r in measurements}),
            source_challenge=challenge,challenge_compound_id=compound,
            charge_pre=step[0],charge_post=step[1],measurement_count=len(measurements),
            geometry_dataset='pKahub',geometry_record_id=anchor['record_id'],
            source_record_ids=[r['record_id'] for r in measurements],
            source_rows=[r['source_row'] for r in measurements],
            source_values=[r['value'] for r in measurements],
            model_smiles=anchor['model_smiles'],
            atom_site_id=None,microscopic_assignment_performed=False))
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--attempt',required=True)
    p.add_argument('--quota-snapshot',type=Path,required=True)
    a=p.parse_args()
    def safe():capacity(a.root,a.quota_snapshot,needed=268435456)
    safe();out=a.root/'directive19/pKahub'/a.attempt;out.mkdir(parents=True,exist_ok=False)
    progress=json.loads((a.root/'progress_20261119_03.json').read_text())
    domain=json.loads(Path(progress['domains']['pKahub']['manifest']).read_text())
    overlay=json.loads(Path(progress['supplemental_sources']['SAMPL6_7']).read_text())
    blind=[];source_membership=defaultdict(list);blind_keys=set()
    for row in pq.read_table(overlay['records']).to_pylist():
        key=full_key(row['original_smiles'],row['original_InChIKey']);blind_keys.add(key)
        blind.append(dict(source_challenge=row['source_challenge'],
            challenge_compound_id=row['challenge_compound_id'],rawdataID=row['rawdataID'],
            full_InChIKey=key,original_smiles=row['original_smiles']))
        for link in json.loads(row['unified_links_json']):
            source_membership[link['unified_source_row']].append((row['source_challenge'],row['challenge_compound_id']))
    groups=defaultdict(list);challenge_groups=defaultdict(list);excluded=[];unknown=[];counts=Counter();keys={}
    for batch in pq.ParquetFile(domain['records']).iter_batches(batch_size=2048):
        safe()
        for row in batch.to_pylist():
            counts['source_curated_rows']+=1
            raw=json.loads(row['original_fields_json'])
            if not row['domain_eligible']:
                counts['domain_ineligible_rows']+=1;continue
            smiles=raw['reprSMILES_processed']
            if smiles not in keys:keys[smiles]=full_key(smiles)
            key=keys[smiles];is_blind=key in blind_keys
            if is_blind:
                excluded.append(dict(record_id=row['record_id'],source_row=row['source_row'],
                    molid=raw.get('molid'),source_dataset=raw.get('dataset'),rawdataID=raw.get('rawdataID'),
                    full_InChIKey=key,reason='EXACT_COMPLETE_INCHIKEY_MATCH_TO_SAMPL6_OR_SAMPL7'))
            try:value=float(raw['Exp_Macro_pKa_processed'])
            except (ValueError,TypeError):value=float('nan')
            step=transition(raw.get('assigned_charge_state_transition'))
            if not math.isfinite(value) or endpoint(step) is None:
                unknown.append(dict(record_id=row['record_id'],source_row=row['source_row'],
                    reason='NO_FINITE_ASSIGNED_UNIT_DEPROTONATION',transition=raw.get('assigned_charge_state_transition')))
                continue
            measurement=dict(record_id=row['record_id'],source_row=row['source_row'],
                molid=raw.get('molid'),full_InChIKey=key,value=value,
                transition=raw['assigned_charge_state_transition'],model_smiles=row['model_smiles'])
            if not is_blind:groups[key].append(measurement)
            for challenge,compound in source_membership.get(row['source_row'],[]):
                challenge_groups[(challenge,compound)].append(measurement)
    train=[t for key,rows in groups.items() for t in targets_for_group(rows,'TRAIN_POOL',key)]
    test=[t for (challenge,compound),rows in challenge_groups.items()
          for t in targets_for_group(rows,'EXTERNAL_BLIND',challenge+':'+compound,challenge,compound)]
    for name,rows in [('train_macro_targets',train),('blind_macro_targets',test),
                      ('training_exclusions',excluded),('blind_source_identities',blind),('unresolved_measurements',unknown)]:
        safe()
        if rows:pq.write_table(pa.Table.from_pylist(rows),out/(name+'.parquet'),compression='zstd')
        else:(out/(name+'.empty.json')).write_text('[]\n')
    summary=dict(status='MACRO_TARGETS_AND_EXACT_SAMPL_EXCLUSIONS_READY_SITE_EVIDENCE_PENDING',
        source_domain_manifest=progress['domains']['pKahub']['manifest'],
        source_SAMPL_links=progress['supplemental_sources']['SAMPL6_7'],
        training_targets=str(out/'train_macro_targets.parquet'),blind_targets=str(out/'blind_macro_targets.parquet'),
        training_exclusions=str(out/'training_exclusions.parquet'),blind_identities=str(out/'blind_source_identities.parquet'),
        counts=dict(counts),training_molecules=len(groups),external_challenge_compounds=len(challenge_groups),
        training_endpoints=dict(Counter(r['endpoint'] for r in train)),blind_endpoints=dict(Counter(r['endpoint'] for r in test)),
        blind_complete_InChIKeys=len(blind_keys),excluded_source_rows=len(excluded),unresolved_measurements=len(unknown),
        strongest_transition_rule='Acid: minimum transition mean for q_pre<=0; base: maximum transition mean for q_pre>0; q_pre-q_post=1',
        replicate_rule='Arithmetic mean of author-curated experimental measurements assigned to the same molecule and charge transition; all source values/IDs retained',
        replicate_rule_reference='https://github.com/keserulab/pkahub/blob/93958c195874f0a248b2448341cabd58b1f3c7a7/tools/translate.py#internaldict_to_molvis_input',
        extra_temperature_or_numeric_outlier_filters=False,
        exact_blind_exclusion='Complete 27-character InChIKey, including stereo and protonation blocks; no connectivity-only match',
        source_graphs_or_original_measurements_deleted=False,
        single_site_certified_subset=0,single_site_status='NO_EXPERIMENTAL_ATOM_SITE_EVIDENCE_IN_B0_EXPORT; not a claim that no single-site molecules exist',
        multi_site_molecule_count=None,multi_site_count_status='NOT_ESTABLISHED_BY_MACRO_TRANSITION_COUNTS',
        experimental_micro_records=0,predicted_microspecies_used_as_experimental=False,
        microscopic_assignment_performed=False,scientific_decisions_pending=False,
        geometry='Existing shared Sprime/D by geometry_dataset + geometry_record_id; no new geometries',
        independent_numeric_readback=False,new_data_content_hashes=False)
    safe();(out/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('PKA_MACRO_TARGETS_CLOSED',out/'manifest.json',summary['training_endpoints'],summary['blind_endpoints'],flush=True)

if __name__=='__main__':main()
