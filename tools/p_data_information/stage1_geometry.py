"""Label-blind panel and geometry producer; no P label arrays retained."""
import collections,hashlib,itertools,json,os,pathlib,sys,time
import numpy as np
from stage0_cohort import R,D,O,P,load,save,guard
sys.path.insert(0,str(R/'MFM_p_data_information/current'))
from phychem_mfm.phase1.v31_loader import MFM4Dataset
from physical_pair_identity import select_pairs,read_native_ids
SEED=20261025
def key(role,panel,identity):return hashlib.sha256(json.dumps(['P-DATA-INFORMATION-v1',SEED,role,panel,identity],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def rmsd(a,b,heavy):
 a=np.asarray(a,dtype=np.float64)[heavy];b=np.asarray(b,dtype=np.float64)[heavy]
 if len(a)==0:return None
 a=a-a.mean(0);b=b-b.mean(0);u,s,v=np.linalg.svd(a.T@b);u[:,-1]*=np.linalg.det(u@v);return float(np.sqrt(np.mean(np.sum((a@u@v-b)**2,axis=1))))
def local_setup(m,role,mid):
 z=m[1];adj={i:set() for i in range(len(z))}
 for a,b in m[2]:adj[int(a)].add(int(b));adj[int(b)].add(int(a))
 pairs=[]
 for a in range(len(z)):
  if z[a]==1:continue
  reached={a};front={a}
  for _ in range(2):front=set.union(set(),*(adj[x] for x in front))-reached;reached|=front
  pairs.extend((a,b) for b in range(a+1,len(z)) if z[b]>1 and b not in reached)
 pairs=sorted(pairs,key=lambda p:(key(role,'nonbond_contact',[mid,*p]),p))[:128]
 torsions=[]
 for (a,b),order in zip(m[2],m[3]):
  a,b=int(a),int(b)
  if order!=1 or z[a]==1 or z[b]==1:continue
  left=sorted(x for x in adj[a]-{b} if z[x]>1);right=sorted(x for x in adj[b]-{a} if z[x]>1)
  if not left or not right:continue
  reached={a};front={a}
  while front:
   nxt=set()
   for x in front:
    for y in adj[x]:
     if {x,y}=={a,b}:continue
     if y not in reached:nxt.add(y)
   reached|=nxt;front=nxt
  if b in reached:continue
  torsions.append((left[0],a,b,right[0]))
 return pairs,torsions

def angle(pos,ids):
 p=np.asarray(pos,dtype=np.float64)[list(ids)];b0=-(p[1]-p[0]);b1=p[2]-p[1];b2=p[3]-p[2]
 if np.linalg.norm(b1)==0:return None
 b1/=np.linalg.norm(b1);v=b0-np.dot(b0,b1)*b1;w=b2-np.dot(b2,b1)*b1
 if min(np.linalg.norm(v),np.linalg.norm(w))<1e-12:return None
 return float(np.arctan2(np.dot(np.cross(b1,v),w),np.dot(v,w)))

def local_difference(a,b,contacts,torsions):
 distances=[abs(float(np.linalg.norm(a[i]-a[j])-np.linalg.norm(b[i]-b[j]))) for i,j in contacts]
 changes=[]
 for ids in torsions:
  x,y=angle(a,ids),angle(b,ids)
  if x is not None and y is not None:changes.append(abs(float(np.arctan2(np.sin(x-y),np.cos(x-y))))*180/np.pi)
 return dict(contact_pairs=len(distances),contact_distance_rms=float(np.sqrt(np.mean(np.square(distances)))) if distances else None,rotatable_dihedrals=len(torsions),valid_dihedrals=len(changes),dihedral_change_median_deg=float(np.median(changes)) if changes else None,dihedral_change_max_deg=max(changes) if changes else None)

def main():
 started=time.time();mother=load(O/'mother_metadata.json');panels={};summary={};allpairs={}
 for role,rows in mother.items():
  eligible=[r for r in rows if r['status']=='eligible'];core=eligible[:3000 if role=='TRAIN' else 300];groups=collections.defaultdict(lambda:collections.defaultdict(list))
  for r in eligible:groups[r['formula_charge']][r['graph']].append(r)
  selected=[]
  for formula,graphs in groups.items():
   if len(graphs)<2:continue
   reps=[min(rs,key=lambda r:(key(role,'isomer_member',r['molecule_id']),r['molecule_id'])) for rs in graphs.values()]
   reps=sorted(reps,key=lambda r:(key(role,'isomer_member',r['molecule_id']),r['molecule_id']))[:4];selected.append((formula,reps))
  selected=sorted(selected,key=lambda g:(key(role,'isomer_group',g[0]),g[0]))[:500 if role=='TRAIN' else 50]
  panel={r['molecule_id']:dict(r,core=True,enriched=False) for r in core}
  for formula,reps in selected:
   for r in reps:panel.setdefault(r['molecule_id'],dict(r,core=False,enriched=False))['enriched']=True
  ds=MFM4Dataset(P,split=role,geometry_only=True,k=10,molecule_indices=[r['pilot_index'] for r in panel.values()]);geometries={};counts=collections.Counter();conformerpairs=[];geometry_stats=[]
  allowed={(r['pilot_index'],int(ci)) for r in panel.values() for ci in ds.choices(r['pilot_index'])};native_ids=read_native_ids(P,role,list(panel.values()),allowed)
  for n,(mid,r) in enumerate(panel.items()):
   guard();mi=r['pilot_index'];m=ds.record('M',mi);choices=list(map(int,ds.choices(mi)));r['allowed_conformers']=choices;r['heavy_atoms']=int((m[1]>1).sum());r['atom_count']=len(m[1]);r['elements']=m[1].tolist();r['bonds']=m[2].tolist();r['bond_order']=m[3].tolist()
   raw_geometries={ci:ds.record('P',mi,ci) for ci in choices};c={ci:a[21] for ci,a in raw_geometries.items()};heavy=m[1]>1;representatives=[];pair_metrics={};contacts,torsions=local_setup(m,role,mid)
   for ci in choices:
    if not any(rmsd(c[ci],c[rj],heavy)<.5 for rj in representatives):representatives.append(ci)
   for ca,cb in itertools.combinations(choices,2):
    pair_metrics[(ca,cb)]=dict(heavy_rmsd=rmsd(c[ca],c[cb],heavy),all_atom_rmsd=rmsd(c[ca],c[cb],np.ones(len(heavy),dtype=bool)),exact_stored_geometry=bool(np.array_equal(c[ca],c[cb])))
   mapping={ci:native_ids[(mi,ci)] for ci in choices};selected_pairs=[(a,b) for a,b,identity in select_pairs(role,mid,mapping)]
   for ca,cb in selected_pairs:conformerpairs.append(dict(molecule_id=mid,a=ca,b=cb,native_record_id_a=mapping[ca],native_record_id_b=mapping[cb],physical_pair_id=[[mid,mapping[ca]],[mid,mapping[cb]]],**pair_metrics[(ca,cb) if (ca,cb) in pair_metrics else (cb,ca)]))
   for pair in conformerpairs[-len(selected_pairs):] if selected_pairs else []:
    pair.update(local_difference(c[pair['a']],c[pair['b']],contacts,torsions))
    ga,gb=raw_geometries[pair['a']].get(22),raw_geometries[pair['b']].get(22)
    pair['perturbed_heavy_rmsd']=rmsd(ga,gb,heavy) if ga is not None and gb is not None else None
   r['representative_count_05A']=len(representatives);geometry_stats.append(dict(molecule_id=mid,records=len(choices),representatives=len(representatives),all_pair_count=len(pair_metrics),pair_heavy_rmsd=[v['heavy_rmsd'] for v in pair_metrics.values()]))
   counts['records']+=len(choices);counts['representatives']+=len(representatives);counts['geometry_comparisons']+=len(pair_metrics)
   if n%250==0:print(role,n,len(panel),flush=True)
  ds.close();isopairs=[dict(formula_charge=f,a=a['molecule_id'],b=b['molecule_id']) for f,reps in selected for a,b in itertools.combinations(reps,2)]
  cross=[];ordered=sorted(core,key=lambda r:(key(role,'composition',r['molecule_id']),r['molecule_id']));used=set()
  for i,a in enumerate(ordered):
   if a['molecule_id'] in used:continue
   b=next((b for b in ordered[i+1:] if b['molecule_id'] not in used and b['formula_charge']!=a['formula_charge']),None)
   if b is not None:cross.append(dict(a=a['molecule_id'],b=b['molecule_id']));used.update([a['molecule_id'],b['molecule_id']])
  panels[role]=list(panel.values());allpairs[role]=dict(conformer=conformerpairs,isomer=isopairs,composition=cross);summary[role]=dict(molecules=len(panel),core=len(core),enriched_groups=len(selected),connection_graphs=len({r['graph'] for r in panel.values()}),**counts,conformer_pairs=len(conformerpairs),isomer_pairs=len(isopairs),composition_pairs=len(cross),geometry=geometry_stats)
 save(O/'panel.json',panels);save(O/'pairs.json',allpairs);save(O/'coverage.json',dict(roles=summary,elapsed_seconds=time.time()-started,label_values_used_for_selection=False,geometry_layer='pilot_MFM4_FP32; authority-route verification pending'))
 print('STAGE1_GEOMETRY_DONE',flush=True)
if __name__=='__main__':main()
