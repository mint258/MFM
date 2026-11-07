"""No new full graph normalization; original keys and conservative source atoms."""
import collections,hashlib,json,re
from workflows.expansion.identity_v2.projection_v2 import full_keys,native_composition,source_smiles_keys
from workflows.expansion.decontamination import identity_keys,ALLOWED_IDENTITY_FIELDS
from workflows.expansion.common import wp5_key
from workflows.expansion.marcel_kraken_decontamination_main_v1.projection import strict_json
from . import contract as C,atoms

def locator(*parts):return json.dumps(parts,ensure_ascii=True,separators=(',',':'))

def strict(name,sid,keys,comp=None):
    valid,bad=full_keys(keys,strict=False);C.need(not bad and valid==keys,'ALL_ORIGINAL_FULL_KEYS_VALID_NO_SELECTION')
    row={'source_id':sid,'role':'all','subdataset':name,'inchikeys':list(keys),'non_h_composition':comp}
    identity_keys(row);C.need(set(row)==ALLOWED_IDENTITY_FIELDS,'ORIGINAL_STRICT5_ONLY');return row

def fallback(texts,Chem):
    values=[];unresolved=[]
    for i,text in enumerate(texts):
        evidence=atoms.composition(text,Chem,{'native_composition':native_composition})
        if evidence.get('composition') is not None:values.append((i,evidence['composition'],evidence))
        else:unresolved.append((i,evidence))
    return values,unresolved

EMPTY={(len(b),hashlib.sha256(b).hexdigest()) for b in (b'\n',b'\r',b'\r\n')}

def csv_row(row,ref,Chem):
    source=strict_json(row['source_identity_json']);result=strict_json(row['key_observation_json']);sid=source['source_id'];ordinal=source['source_row_ordinal']
    C.need(sid in C.CSV and type(ordinal)is int and 1<=ordinal<=C.CSV[sid][1] and source['role']==row['role']=='ALLSPLITS'
      and result['source']==source and row['source_id']==sid and row['source_row_ordinal']==ordinal
      and row['full_keys']==result['SMILES_derived_full_keys'] and row['WP5_keys']==result['WP5_keys']
      and result['physical_identity']==row['physical_identity']==sid+':'+str(ordinal)
      and all(row[k]==source[k] for k in ('source_offset','source_record_bytes','source_record_sha256')),
      'EXACT_NORMALIZED_SOURCE_ROW_AND_ALL_KEYS_NOT_JOURNAL_ALIAS')
    fields=list(source['identity_fields'].values());name=C.CSV[sid][0];base=locator('MoleculeNet',name,ref['sha256'],ordinal);keys=row['full_keys']
    empty=(source['field_count']==1 and (source['source_record_bytes'],source['source_record_sha256']) in EMPTY
      and all(f['state'] in ('EMPTY','MISSING') and f['text'] in ('',None) for f in fields))
    C.need(not(empty and keys),'EMPTY_SPAN_CANNOT_CARRY_KEYS')
    if empty:return [],{'classification':'EXACT_LITERAL_EMPTY_ORIGINAL_RECORD_NO_ID_OR_OTHER_FIELD','nonmolecular':True,'unresolved':0}
    if keys:return [strict(name,base,keys)],{'classification':'ALL_ORIGINAL_KEYS_RETAINED','nonmolecular':False,'unresolved':0}
    smiles=[v for v in fields if v['literal_column_name']=='smiles'];C.need(len(smiles)==1,'ONE_ACTUAL_ORIGINAL_SMILES_COLUMN')
    values,unknown=fallback([smiles[0]['text']],Chem)
    return [strict(name,base,[],c) for _,c,_ in values],{'classification':'ORIGINAL_UNRESOLVED_GRAPH_ATOMS_ONLY_OR_HOLD',
      'nonmolecular':False,'unresolved':len(unknown),'atoms_evidence':[e for _,_,e in values]+[e for _,e in unknown]}

def local_row(row,ref,ordinal,Chem):
    if row['dataset'] not in C.LOCAL:return [],None
    name=C.LOCAL[row['dataset']][0];C.need(row['role']=='all' and 'all' in row['memberships'],'ALL_ORIGINAL_LOCAL_SPLITS_NOT_EFFECTIVE_TRAIN')
    base=locator('MoleculeNet',name,ref['sha256'],ordinal,row['source_id']);keys=row['inchikeys'];comp=None if row['non_h_composition_json'] is None else strict_json(row['non_h_composition_json'])
    original={k:row[k] for k in ('role','memberships','missing_full_key','missing_identity_or_composition','unresolved_source_variant','conservative_reason',
      'smiles_variants','source_metadata_json')}
    if keys or comp is not None:return [strict(name,base,keys,comp)],{'dataset':row['dataset'],'unresolved':0,'original_status_and_identity_metadata':original}
    values,unknown=fallback(row['smiles_variants'],Chem)
    return [strict(name,base+':unresolved_variant:'+str(i),[],c) for i,c,_ in values],{'dataset':row['dataset'],
      'unresolved':len(unknown) or int(not values),'original_graph_state':'UNKNOWN_UNCHANGED','original_status_and_identity_metadata':original,
      'atoms_evidence':[e for _,_,e in values]+[e for _,e in unknown]}

def native_union(value,ref,ordinal):
    entity=value['entity_identity'];C.need(type(entity)is list and entity and value['same_ID_implies_same_graph'] is False
      and value['full_or_pool_acceptance'] is False and value['MOL2_partial_charge_is_formal_charge'] is False,'ORIGINAL_NATIVE_ENTITY_UNION_NOT_GRAPH_EQUIVALENCE')
    members=value['members'];C.need(len(members)==value['physical_record_count'] and len({m['record_id'] for m in members})==len(members),'ALL_ORIGINAL_PHYSICAL_NATIVE_MEMBERS')
    sources=collections.Counter(m['source_id'] for m in members);C.need(dict(sources)==value['source_component_counts'],'ALL_COMPONENT_VARIANTS_RETAINED')
    name='QM8' if set(sources)=={'qm8_sdf'} else 'PDBbind';C.need(name!='PDBbind' or set(sources)<={'pdbbind_core','pdbbind_general','pdbbind_refined'},'NO_NATIVE_DATASET_ALIAS')
    base=locator('MoleculeNet',name,ref['sha256'],ordinal,entity);keys=value['all_observed_full_key_union']
    C.need(value['all_observed_WP5_union']==sorted({wp5_key(k) for k in keys}),'EXACT_ORIGINAL_NATIVE_AND_SOURCE_KEY_UNION')
    rows=[strict(name,base,keys)] if keys else [];unknown=0
    for i,part in enumerate(value['unresolved_variant_composition_evidence']):
        comp=part['native_non_H_composition_evidence']
        if comp is None:unknown+=1
        else:rows.append(strict(name,base+':original_unresolved_variant:'+str(i),[],comp))
    if not rows and not unknown:unknown=1
    return rows,{'entity_identity':entity,'native_members':len(members),'component_counts':dict(sources),
      'unresolved':unknown,'original_graph_UNKNOWN_retained':bool(value['unresolved_variant_composition_evidence'])}

def formula(text,Chem):
    C.need(type(text)is str and text and len(text)<=1024,'EXACT_OFFICIAL_LIGAND_FORMULA')
    counts=collections.Counter();table=Chem.GetPeriodicTable()
    for word in text.split():
        m=re.fullmatch(r'([A-Z][a-z]?)([1-9][0-9]*)?',word);C.need(m is not None,'UNKNOWN_FORMULA_GRAMMAR_NO_GUESS')
        symbol,n=m.groups();z=table.GetAtomicNumber(symbol);C.need(1<=z<=118 and table.GetElementSymbol(z)==symbol,'EXACT_FORMULA_ELEMENT')
        counts[z]+=int(n or '1')
    return native_composition(dict(counts))

def mass(local,csv,native,index,quantum):
    C.need(dict(local)=={k:v[1] for k,v in C.LOCAL.items()} and dict(csv)=={k:v[1] for k,v in C.CSV.items()},'EXACT_FULL_LOCAL6_AND_CSV6_PHYSICAL_COUNTS')
    C.need(native==57480 and dict(index)==C.IDS and quantum=={'QM7':7165,'QM9':133885,'QM7b':7211},'ALL_NATIVE_CONTEXT_INDEX_AND_QUANTUM_POPULATIONS')
    return {'all17_dataset_names':list(C.NAMES),'local6_physical_rows':sum(local.values()),'CSV6_physical_rows':sum(csv.values()),
      'native_physical_context_records':native,'original_index_records':sum(index.values()),'quantum_records':quantum,
      'physical_rows_are_not_unique_molecules':True,'original39633_is_not17_dataset_coverage':True}
