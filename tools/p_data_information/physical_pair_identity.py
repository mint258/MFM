"""Taskbook v1 physical pair identities, independent of export numbering."""
import hashlib,itertools,json
VERSION='P-DATA-INFORMATION-v1';SEED=20261025
def physical_pair(mid,a,b):return [[mid,x] for x in sorted([a,b])]
def select_pairs(role,mid,ids):
 if len(set(ids.values()))!=len(ids):raise ValueError('Ambiguous native identity within molecule')
 candidates=[]
 for a,b in itertools.combinations(ids,2):
  if ids[a]==ids[b]:continue
  if ids[b]<ids[a]:a,b=b,a
  identity=physical_pair(mid,ids[a],ids[b]);h=hashlib.sha256(json.dumps([VERSION,SEED,role,'conformer_pair',identity],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest();candidates.append((h,identity,a,b))
 return [(a,b,identity) for _,identity,a,b in sorted(candidates)[:6]]
def read_native_ids(root,role,panel,allowed):
 import pyarrow.dataset as pad
 mids=[r['molecule_id'] for r in panel];expr=(pad.field('record_kind')=='P')&pad.field('molecule_id').isin(mids);options=pad.ParquetFragmentScanOptions(pre_buffer=False);source=pad.dataset(root/('v31_pilot_'+role)/'id_map.parquet',format='parquet');ids={}
 scan=source.scanner(columns=['molecule_index','conformer_index','native_record_id'],filter=expr,batch_size=128,use_threads=False,batch_readahead=0,fragment_readahead=0,fragment_scan_options=options)
 for batch in scan.to_batches():
  for r in batch.to_pylist():
   address=(int(r['molecule_index']),int(r['conformer_index']))
   if address in allowed and r['native_record_id']:
    if address in ids:raise ValueError('Ambiguous frozen pilot address')
    ids[address]=r['native_record_id']
 missing=allowed-ids.keys()
 if missing:
  scan=source.scanner(columns=['molecule_index','conformer_index','legacy_geometry_ids'],filter=expr&pad.field('native_record_id').is_null(),batch_size=128,use_threads=False,batch_readahead=0,fragment_readahead=0,fragment_scan_options=options)
  for batch in scan.to_batches():
   for r in batch.to_pylist():
    address=(int(r['molecule_index']),int(r['conformer_index']))
    if address in missing:
     bases=sorted(g for g in r['legacy_geometry_ids'] if g.startswith('pm7:'))
     if bases:ids[address]='geometry:'+bases[0]
 if set(ids)!=allowed:raise ValueError('Stable physical identities not resolved; never substitute local indices')
 return ids
