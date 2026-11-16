"""Original F64 local/vector/pair cells on frozen records, using exact witnesses.
The SQLite file is a bounded selected-label cache, never a source-wide index.
"""
import collections,functools,hashlib,json,pathlib,pickle,sqlite3,sys,time
import numpy as np
import zlib,subprocess
import pyarrow.parquet as pq
from stage0_cohort import R,O,load,save,guard
from source_point_scalars import original,SNAP
B=R/'MFM_p_data_information';sys.path.insert(0,str(SNAP))
from workflows.data_v1_final.labels.window2_r73_views_v1.kernel import derive_entries,derived_fields
FAMILY={'pm7_B':'pm7_neutral','pm7_anion':'pm7_ions','pm7_cation':'pm7_ions','pm7_water':'pm7_solvents','pm7_octanol':'pm7_solvents','xtb_singlepoint':'xtb_singlepoint','xtb_ALPB_water':'xtb_alpb','xtb_ALPB_octanol':'xtb_alpb','xtb_fod':'xtb_fod','xtb_perturbed_gradient':'perturbed','xtb_vipea':'xtb_vipea','xtb_vfukui':'xtb_vfukui'}
@functools.lru_cache(maxsize=96)
def cached_samples(role,mi):
 with (O/'samples'/role/(str(mi)+'.pkl')).open('rb') as stream:return pickle.load(stream)
def packed(field,values,indices,native,context,template,pair_override=None):
 p=context['source_to_M'];n=len(p);level=field['level'];ends=None;reason=None
 vals=np.asarray([np.nan if v is None else v for v in values],dtype=np.float64)
 if level in ('molecule_vector','molecule_tensor','molecule'):
  if len(vals)!=1:return None,'Unsupported graph component shape'
  raw=vals.reshape(1,1)
 elif level=='atom_vector':
  if len(vals)!=3*n:return None,'Source vector atom count mismatch'
  raw=np.empty((n,3),dtype=np.float64);raw[p]=vals.reshape(n,3)
 elif level=='atom':
  if len(vals)!=len(indices) or any(type(i)is not int or not 0<=i<n for i in indices):return None,'Source atom-index shape/range mismatch'
  if len(set(indices))!=len(indices):return None,'Duplicate source atom indices'
  raw=np.full((n,1),np.nan);raw[p[np.asarray(indices,dtype=int)],0]=vals
 elif level=='sparse_atom_pair':
  if pair_override is not None:ep=pair_override
  else:
   keys=('atom_i','atom_j') if field['registry_id']==73 else ('i','j');ep=[[r.get(keys[0]),r.get(keys[1])] for r in native] if isinstance(native,list) else []
  if len(ep)!=len(vals) or any(type(i)is not int or not 0<=i<n for e in ep for i in e):return None,'Source pair endpoint shape/range mismatch'
  if len({tuple(e) for e in ep})!=len(ep):return None,'Unresolved repeated source directed endpoint'
  ends=p[np.asarray(ep,dtype=int).reshape(-1,2)];raw=vals.reshape(-1,1)
 else:return None,'Unsupported original field level: '+str(level)
 if ends is None:
  if raw.shape!=template.raw.shape:return None,'Source/pilot target dimensions differ'
  valid=np.isfinite(raw)&template.valid
 else:
  old={tuple(e):i for i,e in enumerate(template.pair_index.tolist())} if template.pair_index is not None else {};valid=np.zeros_like(raw,dtype=bool)
  for i,e in enumerate(ends.tolist()):
   j=old.get(tuple(e))
   if j is not None:valid[i]=np.isfinite(raw[i])&template.valid[j]
 return dict(raw=raw,valid=valid,pair_index=ends,source_finite=np.isfinite(raw)),reason

def main():
 started=time.time();guard();initial_usage=int(subprocess.check_output(['du','-s','-B1',str(O)],text=True).split()[0]);existing_db=(O/'source_local_authority.sqlite').stat().st_size if (O/'source_local_authority.sqlite').exists() else 0;other_bytes=initial_usage-existing_db;panels=load(O/'panel.json');ids=load(O/'pilot_physical_ids.json');defs=load(B/'configs/p_data_information/fields.json')['fields'];wanted_names={f['field_key'] for f in defs if f['level'] in ('atom','pair')};unresolved_vectors=[f['field_key'] for f in defs if f['level'] not in ('molecule','atom','pair')];coverage=load('/lfshome/zixiao/data_v1_20261025/full_projection_coverage_20261105_r2/manifest.json');allfields=load(coverage['field_map_reference']['path']);allfields=allfields['fields'] if isinstance(allfields,dict) else allfields;bytask=collections.defaultdict(list);r73=next(f for f in allfields if f.get('registry_id')==73 and f['field_id']<146)
 for f in allfields:
  if f['field_key'] in wanted_names:bytask[f['field_key'].split('.')[1]].append(f)
 derived=derived_fields([r73]);assert {f['field_key'] for f in derived}<wanted_names;covered={f['field_key'] for fs in bytask.values() for f in fs}|{f['field_key'] for f in derived};assert covered==wanted_names
 with (O/'source_scalar_selected_locators.pkl').open('rb') as stream:point=pickle.load(stream)
 wanted={(r['molecule_id'],ids[role][r['molecule_id']][str(ci)]):(role,r['pilot_index'],ci) for role,rows in panels.items() for r in rows for ci in r['allowed_conformers']};assert {k:(v[0],v[2]) for k,v in wanted.items()}==point['wanted'];families={FAMILY[t] for t in bytask};families.add('pm7_neutral');eligible=[(f,g) for f,g in point['locator'].items() if point['files'][f]['family'] in families]
 with (O/'source_selected_unique_permutations.pkl').open('rb') as stream:permutation_cache=pickle.load(stream)
 assert permutation_cache['wanted']==wanted
 dbpath=O/'source_local_authority.sqlite';c=sqlite3.connect(dbpath);c.execute('PRAGMA journal_mode=DELETE');c.execute('PRAGMA synchronous=FULL');c.execute('PRAGMA cache_size=-131072');c.execute('PRAGMA temp_store=MEMORY');c.executescript('CREATE TABLE IF NOT EXISTS labels(role TEXT,mi INTEGER,ci INTEGER,name TEXT,payload BLOB,PRIMARY KEY(role,mi,ci,name)) WITHOUT ROWID; CREATE TABLE IF NOT EXISTS completed(file INTEGER PRIMARY KEY,reference TEXT,counts TEXT);');summary=collections.Counter();field_counts={n:collections.Counter() for n in wanted_names}
 for fi,(fid,groups) in enumerate(eligible):
  guard();ref=point['files'][fid]['reference'];reftext=json.dumps(ref,sort_keys=True);done=c.execute('SELECT reference,counts FROM completed WHERE file=?',(fid,)).fetchone()
  if done:
   assert done[0]==reftext;state=json.loads(done[1]);summary.update(state['summary'])
   for n,v in state['fields'].items():field_counts[n].update(v)
   continue
  q=pq.ParquetFile(ref['path'],pre_buffer=False);assert pathlib.Path(ref['path']).stat().st_size==ref['bytes'];columns=[n for n in ['record_id','molecule_id','calc_type','total_atoms','values','numeric_issues','reproduction_package_sha256','input_file_sha256','input_bundle_sha256','software_version_id','converged','precision_by_field_json'] if n in q.schema_arrow.names];sc=collections.Counter();fc={n:collections.Counter() for n in wanted_names};c.execute('BEGIN')
  try:
   for rg,entries in sorted(groups.items()):
    if other_bytes+dbpath.stat().st_size+1024**3+256*1024**2>16*1024**3:raise OSError('Selected analysis cache would exceed taskbook 16GiB peak')
    guard();table=q.read_row_group(rg,columns=columns,use_threads=False)
    for row,(mid,rid) in entries:
     raw=table.slice(row,1).to_pylist()[0];assert raw['record_id']==rid and raw['molecule_id']==mid;task=raw['calc_type'];fs=bytask.get(task,[])
     if not fs and task!='pm7_B':continue
     role,mi,ci=wanted[(mid,rid)];perm=permutation_cache['maps'][(mid,rid)];sc['candidate_task_rows']+=1;expected={v['name']:v['sha256'] for v in raw.get('input_file_sha256') or []}
     if perm is None or len(perm)!=raw['total_atoms']:sc['unresolved_atom_correspondence_rows']+=1;continue
     ctx=dict(source_to_M=np.asarray(perm,dtype=int));sc['unambiguous_atom_correspondence_rows']+=1
     sample=cached_samples(role,mi)[ci];cells={v['registry_id']:v for v in raw.get('values') or []};decoded={};work=[]
     for f,vals,indices,reason in original.task_components(raw,'REGISTRY_CELL',fs):work.append((f,vals,indices,reason,None))
     if task=='pm7_B':
      native=original.decode_cell(cells.get(73))
      if isinstance(native,list):
       f,vals,ind,reason=next(original.task_components(raw,'REGISTRY_CELL',[r73]));finite=[original.numeric(v) for v in vals];entry=dict(field=r73,values_float64=[v if ok else None for v,ok in zip(vals,finite)],value_mask=finite,source_value_mask=finite,source_reasons=[],new_reasons=[],review_reasons=[])
       for e in derive_entries(native,entry,field_map=derived):work.append((e['field'],e['values_float64'],[None]*len(e['values_float64']),reason,e['pair_indices']))
     for f,vals,indices,decode_reason,ep in work:
      name=f['field_key'];fc[name]['candidate_source_records']+=1;template=sample['targets'].get(name)
      if template is None:fc[name]['pilot_target_missing']+=1;continue
      if f['registry_id'] not in decoded:decoded[f['registry_id']]=original.decode_cell(cells.get(f['registry_id']))
      payload,reason=packed(f,vals,indices,decoded[f['registry_id']],ctx,template,ep)
      if payload is None:fc[name]['unresolved_projection_records']+=1;continue
      if payload['pair_index'] is None:
       oldraw=template.raw
      else:
       oldrows={tuple(e):i for i,e in enumerate(template.pair_index.tolist())};oldraw=np.full(payload['raw'].shape,np.nan)
       for ii,endpoint in enumerate(payload['pair_index'].tolist()):
        jj=oldrows.get(tuple(endpoint))
        if jj is not None:oldraw[ii]=template.raw[jj]
      vv=payload['valid'];fc[name]['common_values_compared']+=int(vv.sum());fc[name]['single_F32_cast_differs_pilot_values']+=int(np.count_nonzero(payload['raw'].astype(np.float32)[vv]!=oldraw[vv]));fc[name]['original_F64_differs_pilot_values']+=int(np.count_nonzero(payload['raw'][vv]!=oldraw[vv]));fc[name]['source_finite_outside_pilot_common_mask']+=int(np.count_nonzero(payload['source_finite']&~vv))
      payload['decode_reason']=decode_reason;payload['source_input_sha256']=expected.get('input.xyz');blob=zlib.compress(pickle.dumps(payload,protocol=5),1);c.execute('INSERT INTO labels VALUES(?,?,?,?,?)',(role,mi,ci,name,blob));fc[name]['projected_records']+=1;fc[name]['common_valid_records']+=int(payload['valid'].any());fc[name]['source_finite_leaves']+=int(payload['source_finite'].sum());fc[name]['common_valid_leaves']+=int(payload['valid'].sum())
    del table
   q.close();state=dict(summary=dict(sc),fields={n:dict(v) for n,v in fc.items() if v});c.execute('INSERT INTO completed VALUES(?,?,?)',(fid,reftext,json.dumps(state)));c.commit();summary.update(sc)
   for n,v in fc.items():field_counts[n].update(v)
  except BaseException:c.rollback();q.close();raise
  if fi%10==0:print('LOCAL_SOURCE_FILE',fi+1,len(eligible),'DB_BYTES',dbpath.stat().st_size,flush=True)
 c.close();save(B/'results/p_data_information/source_local_authority.json',dict(fields={n:dict(v) for n,v in field_counts.items()},summary=dict(summary),cache=str(dbpath),cache_encoding='zlib_pickle_v1',elapsed_seconds=time.time()-started,scope='Coordinate-independent atom/pair scalars only, frozen physical records; original component reader and published r73 F64 kernel; unambiguous recorded atom maps',unresolved_original_vector_fields=unresolved_vectors,vector_reason='Native frame integration producer failed twice; taskbook failure budget exhausted, not retried; pilot aligned-vector evidence remains separate',mask_scope='Common existing pilot masks; numeric source cells do not independently validate original typed-mask policy',global_computation_error_bound=None,actual_new_QM_calls=0));print('SOURCE_LOCAL_AUTHORITY_DONE',flush=True)
if __name__=='__main__':main()