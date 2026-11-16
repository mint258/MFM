# CLOSED FAILED PROTOTYPE: two execution failures; do not retry under TASKBOOK_V1.
# Successful correspondence/native caches and both failure logs are preserved externally.
"""Recover registered native geometries and unambiguous source-to-M mappings.
Only the frozen physical records are cached; no new source-wide index.
"""
import collections,hashlib,json,pathlib,pickle,sqlite3,sys
import numpy as np
from rdkit import Chem
import pyarrow.dataset as pad
import pyarrow.parquet as pq
from stage0_cohort import R,O,P,load,save,guard
from source_point_scalars import db,chunks,cache_save
B=R/'MFM_p_data_information';ROOT=O/'source_native_context'
ENGINE=R/'runs/phase1_wp5_20261011/scripts';sys.path.insert(0,str(ENGINE));import wp5_engine_v3 as engine

def main():
 guard();panels=load(O/'panel.json');ids=load(O/'pilot_physical_ids.json');wanted={};maps={};stats={};mapping_cache=O/'source_selected_unique_permutations.pkl'
 for role,rows in panels.items():
  for row in rows:
   for ci in row['allowed_conformers']:wanted[(row['molecule_id'],ids[role][row['molecule_id']][str(ci)])]=(role,row['pilot_index'],ci)
 if mapping_cache.exists():
  with mapping_cache.open('rb') as stream:cached=pickle.load(stream)
  assert cached['wanted']==wanted;maps=cached['maps'];stats=cached['stats']
 else:
  for role,rows in panels.items():
   count=collections.Counter();mids=[r['molecule_id'] for r in rows];expr=(pad.field('record_kind')=='P')&pad.field('molecule_id').isin(mids);s=pad.dataset(P/('v31_pilot_'+role)/'id_map.parquet',format='parquet').scanner(columns=['molecule_id','native_record_id','molecule_index','conformer_index','atom_permutations'],filter=expr,batch_size=32,use_threads=False,batch_readahead=0,fragment_readahead=0,fragment_scan_options=pad.ParquetFragmentScanOptions(pre_buffer=False))
   for batch in s.to_batches():
    for row in batch.to_pylist():
     key=(row['molecule_id'],row['native_record_id'])
     if key not in wanted:continue
     assert wanted[key]==(role,int(row['molecule_index']),int(row['conformer_index']));perms={tuple(p['source_to_M']) for p in row['atom_permutations']};count['records']+=1
     if len(perms)==1:
      p=next(iter(perms));good=sorted(p)==list(range(len(p)));maps[key]=p if good else None;count['unambiguous_valid_permutations']+=int(good)
     else:maps[key]=None;count['ambiguous_permutation_records']+=1
   stats[role]=dict(count);print(role,'SOURCE_PERMUTATIONS',dict(count),flush=True)
  assert set(maps)==set(wanted);cache_save(mapping_cache,dict(wanted=wanted,maps=maps,stats=stats))
 locator_cache=O/'source_selected_base_locators.pkl'
 if locator_cache.exists():
  with locator_cache.open('rb') as stream:point=pickle.load(stream)
  assert point['wanted']==wanted;files=point['files'];locators=point['locators']
 else:
  m=load('/lfshome/zixiao/data_v1_20261025/D6_full_physical_index_20261105_v3/manifest.json');files={r['id']:r for r in load(m['files_reference']['path'])};ordinals={};c=db(m['canonical_reference']['path'])
  for part in chunks(sorted(wanted,key=lambda k:k[1])):
   marks=','.join('?'*len(part))
   for ordinal,rid,mid in c.execute('SELECT record_ordinal,record_id,molecule_id FROM records WHERE record_id IN ('+marks+')',[k[1] for k in part]):
    if (mid,rid) in wanted:ordinals[ordinal]=(mid,rid)
  c.close();assert len(ordinals)==len(wanted);locators=collections.defaultdict(lambda:collections.defaultdict(list))
  for si,ref in enumerate([m['QC_locations'],*[x['storage'] for x in m['partitions']]]):
   c=db(ref['path'])
   for part in chunks(sorted(ordinals)):
    marks=','.join('?'*len(part))
    for ordinal,f,rg,r in c.execute('SELECT ordinal,file,rg,r FROM locations WHERE domain=0 AND ordinal IN ('+marks+')',part):
     if files[f]['family']=='base_geometry':locators[f][rg].append((r,ordinals[ordinal]))
   c.close();print('SOURCE_BASE_LOCATOR_PART',si,flush=True)
  locators={f:dict(g) for f,g in locators.items()};files={f:files[f] for f in locators};cache_save(locator_cache,dict(wanted=wanted,files=files,locators=locators))
 geometry_cache=O/'source_selected_native_geometries.pkl'
 if geometry_cache.exists():
  with geometry_cache.open('rb') as stream:geometry=pickle.load(stream)
 else:
  geometry={}
  for fi,(fid,groups) in enumerate(locators.items()):
   guard();ref=files[fid]['reference'];assert pathlib.Path(ref['path']).stat().st_size==ref['bytes'];q=pq.ParquetFile(ref['path'],pre_buffer=False)
   for rg,entries in sorted(groups.items()):
    table=q.read_row_group(rg,columns=['record_id','molecule_id','atomic_numbers','positions_A','source_native_geometry_sha256','native_atom_order_sha256'],use_threads=False)
    for row,key in entries:
     raw=table.slice(row,1).to_pylist()[0];assert (raw['molecule_id'],raw['record_id'])==key and key not in geometry;geometry[key]=dict(Z=np.asarray(raw['atomic_numbers'],dtype=np.int16),pos=np.asarray(raw['positions_A'],dtype=np.float64),native_geometry_sha256=raw['source_native_geometry_sha256'],native_atom_order_sha256=raw['native_atom_order_sha256'])
   q.close()
   if fi%25==0:print('SOURCE_NATIVE_GEOMETRY_FILE',fi,len(locators),flush=True)
  assert set(geometry)==set(wanted);cache_save(geometry_cache,geometry)
 protocol_path=R/'runs/phase1_wp5_20261011/configs/protocol.json';protocol=load(protocol_path);protocol_sha=hashlib.sha256(protocol_path.read_bytes()).hexdigest();periodic=Chem.GetPeriodicTable();summary={}
 for role,rows in panels.items():
  c=collections.Counter()
  for ni,row in enumerate(rows):
   guard();mid=row['molecule_id'];mi=row['pilot_index'];path=ROOT/role/(str(mi)+'.pkl')
   if path.exists():
    with path.open('rb') as stream:old=pickle.load(stream)
    c.update(old['counts']);continue
   with (O/'samples'/role/(str(mi)+'.pkl')).open('rb') as stream:pilot=pickle.load(stream)
   records={};unit=collections.Counter()
   for ci in row['allowed_conformers']:
    rid=ids[role][mid][str(ci)];g=geometry[(mid,rid)];p=maps[(mid,rid)];out=dict(native_record_id=rid,valid=False,protocol_sha256=protocol_sha,reason=None);unit['candidate_records']+=1
    if p is None:out['reason']='Ambiguous/invalid source-to-M maps across actual geometry aliases'
    else:
     p=np.asarray(p,dtype=int)
     if len(p)!=len(g['Z']):out['reason']='Source atom count mismatch'
     else:
      Z=np.empty_like(g['Z']);Z[p]=g['Z'];native=dict(symbols=[periodic.GetElementSymbol(int(z)) for z in g['Z']],coords=g['pos']);clean=engine.render_inputs('pm7_B',native,dict(record_id=rid),protocol)['input.xyz'].decode().splitlines()[2:];pert=engine.render_inputs('xtb_perturbed_gradient',native,dict(record_id=rid),protocol)['input.xyz'].decode().splitlines()[2:];clean=np.array([[float(v) for v in line.split()[1:4]] for line in clean]);pert=np.array([[float(v) for v in line.split()[1:4]] for line in pert]);pos=np.empty_like(clean);pos[p]=clean;pospert=np.empty_like(pert);pospert[p]=pert;base=np.empty_like(g['pos']);base[p]=g['pos'];s=pilot[ci]
      valid=bool(np.array_equal(Z,s['Z']) and (np.array_equal(pos.astype(np.float32),s['pos']) or np.array_equal(base.astype(np.float32),s['pos'])));out.update(valid=valid,source_to_M=p,Z=Z,pos=pos,pos_perturbed=pospert,native_geometry_sha256=g['native_geometry_sha256'],native_atom_order_sha256=g['native_atom_order_sha256'],clean_F32_geometry_matches_pilot=valid,perturbed_F32_geometry_matches_pilot=bool(s.get('pos_perturbed') is not None and np.array_equal(pospert.astype(np.float32),s['pos_perturbed'])),reason=None if valid else 'Source Z/base/actual-clean geometry does not exactly reproduce pilot F32 frame')
    if out['valid']:unit['validated_records']+=1;unit['perturbed_exact_matches']+=int(out['perturbed_F32_geometry_matches_pilot'])
    else:unit['unresolved_records']+=1
    records[ci]=out
   cache_save(path,dict(records=records,counts=dict(unit)));c.update(unit)
   if ni%500==0:print(role,'SOURCE_CONTEXT',ni,len(rows),flush=True)
  summary[role]=dict(c)
 save(B/'results/p_data_information/source_atom_correspondence.json',dict(roles=summary,permutation_metadata=stats,external_context=str(ROOT),field_policy='Only unambiguous source-to-M maps with exact Z and source/actual-clean F32 frame reproduction; perturbed frame separately checked',protocol_reference=str(protocol_path),protocol_sha256=protocol_sha,actual_QM_calls=0));print('SOURCE_NATIVE_CONTEXT_DONE',flush=True)
if __name__=='__main__':main()