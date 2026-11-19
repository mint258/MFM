"""Bind PPE author INDEX/charge/spin; preserve original reference XYZ and SI labels."""
import argparse
from collections import Counter
import csv
from decimal import Decimal,InvalidOperation
import io
import json
from pathlib import Path
import time
import zipfile
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from rdkit import Chem
from workflows.expansion.screen import WHITELIST
from .build_csv_domain import SCHEMA
from .domain import assess
from .ppe_graph_source import name_key
from .ppe_reference import target_rows,numeric
from .pprime_queue import capacity
from .reference_mapping import infer_reference_graph,model_graph,map_reference

AUTHOR_MEMBER='PPE1694_G4MP2/PPE1694_G4MP2.csv'
TYPO_ALIASES={
 644:('Tricyclo(5.2.1.0(2,6))decane','Tricyclo[5.2.1.0(2,6))decane'),
 883:('2-[2-(2-hydroxyethoxy)ethoxy]ethanol','2[2-(2-hydroxyethoxy)ethoxy]ethanol'),
}


def geometry_metadata(text):
    fields=text.split(',')
    if len(fields)<6 or (len(fields)-2)%4:raise ValueError('Author Geometry state/atom groups incomplete')
    charge,multiplicity=int(fields[0]),int(fields[1])
    if multiplicity<1:raise ValueError('Author multiplicity invalid')
    z=[Chem.GetPeriodicTable().GetAtomicNumber(s) for s in fields[2::4]]
    if any(n<1 for n in z):raise ValueError('Author element symbol invalid')
    return charge,multiplicity,z


def exact_number_equal(a,b):
    try:return Decimal(str(a)).is_finite() and Decimal(str(a))==Decimal(str(b))
    except (InvalidOperation,ValueError):return False


def target_binding(index,geometry_name,target_name,source_expt,target_expt,formula_bound):
    if name_key(geometry_name)==name_key(target_name):return True,'Original author ordinal and normalized exact name'
    alias=TYPO_ALIASES.get(index)
    if (alias and name_key(geometry_name)==name_key(alias[0]) and name_key(target_name)==name_key(alias[1])
            and formula_bound and exact_number_equal(source_expt,target_expt)):
        return True,'Specific documented punctuation typo; author INDEX, atom composition and exact Expt agree'
    return False,'Unresolved original source identity; no fuzzy name match'


def binding_from_inferred(reference,smiles,numbers,xyz):
    ordered,model=model_graph(smiles)
    match=reference.GetSubstructMatch(model,useChirality=True)
    if len(match)!=len(numbers) or len(set(match))!=len(match):raise ValueError('Inferred reference graph has no full model correspondence')
    if any(model.GetAtomWithIdx(i).GetAtomicNum()!=int(numbers[j]) for i,j in enumerate(match)):
        raise ValueError('Inferred reference/model atomic identities differ')
    return {'model_smiles':ordered,'model_to_reference':list(match),
        'reference_bond_pairs':sorted(tuple(sorted((match[b.GetBeginAtomIdx()],match[b.GetEndAtomIdx()]))) for b in model.GetBonds())}


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path)
    p.add_argument('--attempt',required=True);p.add_argument('--quota-snapshot',required=True,type=Path)
    a=p.parse_args();root=a.root
    def safe():
        waiting=False
        while True:
            try:capacity(root,a.quota_snapshot,67108864);return
            except (OSError,ValueError,KeyError,RuntimeError) as exc:
                if not waiting:print('PPE_STATE_DISK_WAIT',repr(exc),flush=True)
                waiting=True;time.sleep(2)
    safe();out=root/'domain/PPE1694'/a.attempt;out.mkdir(parents=True,exist_ok=False)
    previous={r['record_id']:r for r in pq.read_table(root/'domain/PPE1694/job_4536479/all_rows.parquet').to_pylist()}
    archive=root/'raw/PPE1694_Pople_original_G4MP2/PPE1694_G4MP2.zip'
    author={}
    with zipfile.ZipFile(archive) as z:
        with z.open(AUTHOR_MEMBER) as b:
            for row in csv.DictReader(io.TextIOWrapper(b,encoding='utf-8-sig')):
                index=int(row['INDEX'])
                if index in author:raise ValueError('Duplicate author INDEX')
                charge,mult,numbers=geometry_metadata(row['Geometry'])
                author[index]={'charge':charge,'multiplicity':mult,'atomic_numbers':numbers,'expt':row['expt']}
    if set(author)!=set(range(1,1695)):raise ValueError('Original author INDEX population differs')
    with (root/'raw/PPE1694/SI_review_23_12_2020.txt').open() as f:methods,targets=target_rows(iter(f))
    rows=[];bindings=[];target_output=[];counts=Counter();reasons=Counter();primary=Counter();pending=[]
    reference=root/'reference/PPE1694/job_4536464/reference.parquet'
    for batch in pq.ParquetFile(reference).iter_batches(batch_size=32):
        for ref in batch.to_pylist():
            index=ref['source_frame']+1;meta=author[index];old=previous[ref['record_id']];target=targets[index]
            numbers=ref['atomic_numbers'];formula_bound=Counter(meta['atomic_numbers'])==Counter(numbers)
            bound,rule=target_binding(index,ref['system_name'],target['name'],meta['expt'],target['lexemes']['Expt'],formula_bound)
            values={k:numeric(v) for k,v in target['lexemes'].items()} if bound else {}
            expt,pm7=values.get('Expt'),values.get('PM7')
            target_output.append({'record_id':ref['record_id'],'source_target_row_id':index,
                'geometry_name':ref['system_name'],'target_name':target['name'],'target_name_bound':bound,'binding_rule':rule,
                'original_lexemes_json':json.dumps(target['lexemes']),'experimental_DeltaHf_kcal_mol':expt,
                'published_PM7_DeltaHf_kcal_mol':pm7,
                'residual_experimental_minus_published_PM7_kcal_mol':expt-pm7 if expt is not None and pm7 is not None else None})
            row=dict(old);state='AUTHOR_STATE_GRAPH_PENDING';issues=[];mapping=None;domain=None
            known=list(ref['known_domain_rejection_reasons'])
            if meta['charge']!=0:known.append('NONZERO_CHARGE')
            if meta['multiplicity']!=1:known.append('NON_SINGLET_OR_UNKNOWN')
            known=list(dict.fromkeys(known))
            if not formula_bound:state='AUTHOR_INDEX_REFERENCE_FORMULA_UNRESOLVED';issues.append(state)
            elif known:state='AUTHOR_STATE_KNOWN_REJECTED'
            else:
                try:
                    smiles=old['model_smiles'];inferred=None
                    if not smiles:
                        inferred=infer_reference_graph(numbers,ref['coordinates_A'],meta['charge'])
                        smiles=Chem.MolToSmiles(inferred,canonical=False,isomericSmiles=True)
                    domain=assess(smiles,multiplicity=meta['multiplicity'])
                    if domain['charge']!=meta['charge']:raise ValueError('Author charge and recovered chemical graph differ')
                    state='AUTHOR_STATE_GRAPH_CLASSIFIED'
                    # Preserve the old ordered model SMILES and therefore its already computed D20 identity.
                    if old['model_smiles']:
                        domain['model_smiles']=old['model_smiles'];domain['model_atom_to_source']=old['model_atom_to_source']
                    if domain['domain_eligible']:
                        try:
                            mapping=(binding_from_inferred(inferred,domain['model_smiles'],numbers,ref['coordinates_A']) if inferred is not None
                                else map_reference(domain['model_smiles'],numbers,ref['coordinates_A']))
                        except Exception as exc:issues.append('REFERENCE_ATOM_BINDING:'+type(exc).__name__+':'+str(exc))
                except Exception as exc:state='AUTHOR_STATE_GRAPH_UNRESOLVED';domain=None;issues.append(type(exc).__name__+':'+str(exc))
            if domain is not None:
                row.update({key:domain[key] for key in ('model_smiles','model_atom_to_source','heavy_atoms','charge','salt_removed','domain_eligible','retained','blind_fallback_required')})
                row['original_smiles']=domain['original_smiles'];rs=domain['reasons']
            else:
                row.update(domain_eligible=False,retained=False,charge=meta['charge']);rs=known
                if not known:pending.append({'record_id':ref['record_id'],'state':state,'issues':issues})
            row['exclusion_reasons']=rs;reasons.update(rs)
            if rs:primary[rs[0]]+=1
            metadata=json.loads(row['original_fields_json']);metadata.update(author_state_source=str(archive),author_state_member=AUTHOR_MEMBER,
                author_INDEX=index,declared_charge=meta['charge'],declared_multiplicity=meta['multiplicity'],
                author_reference_formula_bound=formula_bound,graph_metadata_state=state,target_name_bound=bound,
                graph_to_reference_atom_binding='EXPLICIT_MAP' if mapping else 'UNRESOLVED',
                reference_coordinates_regenerated=False,issues=issues)
            row['original_fields_json']=json.dumps(metadata);rows.append(row)
            bindings.append({'record_id':ref['record_id'],'model_smiles':mapping['model_smiles'] if mapping else None,
                'model_to_reference':mapping['model_to_reference'] if mapping else None,
                'reference_bond_pairs':mapping['reference_bond_pairs'] if mapping else None,
                'state':'REFERENCE_MAP_READY' if mapping else state,'issues':issues})
            counts[state]+=1;counts['domain_eligible']+=row['domain_eligible'];counts['target_bound']+=bound
            counts['reference_map_ready']+=bool(mapping)
        safe();print('PPE_AUTHOR_STATE_PROGRESS',len(rows),dict(counts),flush=True)
    if len(rows)!=1694:raise ValueError('PPE reference population changed')
    safe();records=out/'all_rows.parquet';targets_path=out/'target_name_overlay.parquet';maps=out/'reference_bindings.parquet'
    pq.write_table(pa.Table.from_pylist(rows,schema=SCHEMA),records,compression='zstd')
    pq.write_table(pa.Table.from_pylist(target_output),targets_path,compression='zstd')
    map_schema=pa.schema([('record_id',pa.string()),('model_smiles',pa.string()),('model_to_reference',pa.list_(pa.int32())),
        ('reference_bond_pairs',pa.list_(pa.list_(pa.int32(),2))),('state',pa.string()),('issues',pa.list_(pa.string()))])
    pq.write_table(pa.Table.from_pylist(bindings,schema=map_schema),maps,compression='zstd')
    report={'status':'DOMAIN_PARTIAL_EXPLICIT_GRAPH_UNRESOLVED' if pending else 'DOMAIN_READY_REFERENCE_GEOMETRY_UNCHANGED',
        'dataset':'PPE1694','records':str(records),'target_name_overlay':str(targets_path),'reference_bindings':str(maps),
        'counts':[{'before':len(rows),'domain_eligible':counts['domain_eligible'],'retained':counts['domain_eligible'],
            'reason_counts_nonexclusive':dict(reasons),'primary_reason_counts':dict(primary),'graph_metadata_pending':len(pending)}],
        'states':dict(counts),'unresolved_name_graphs':pending,'name_matched_targets':counts['target_bound'],
        'domain_filter_complete':not pending,'author_state_source':str(archive),'author_state_member':AUTHOR_MEMBER,
        'target_values_modified':False,'author_expt_used_as_new_target':False,'methods':methods,
        'reference_geometry_source':str(reference),'reference_geometry_regenerated':False,'independent_numeric_readback':False,
        'old_closed_D20_recomputed':False,'new_data_content_hashes':False,'P_D_ready':False}
    safe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PPE_AUTHOR_STATE_CLOSED',dict(counts),'unresolved',len(pending),flush=True)

if __name__=='__main__':main()