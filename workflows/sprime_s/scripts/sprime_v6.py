"""ETKDGv3/UFF S-prime generator preserving source atom order and stereochemistry."""
from __future__ import annotations
import argparse,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,pickle,time
from collections import OrderedDict
from pathlib import Path
import numpy as np
from prepare import PROJECT,ROOT,save,sha

HANDLES=OrderedDict()

def plain(v): return v.detach().cpu().numpy() if hasattr(v,'detach') else np.asarray(v)
def field(d,k): return d.get(k) if isinstance(d,dict) else getattr(d,k,None)

def read(row):
    import lmdb
    path=Path(row['source_path']);path=path if path.is_absolute() else PROJECT/path
    key=str(path)
    if key not in HANDLES:
        if len(HANDLES)>=4: HANDLES.popitem(last=False)[1].close()
        HANDLES[key]=lmdb.open(key,subdir=False,readonly=True,lock=False,create=False,readahead=False,max_readers=1024)
    env=HANDLES.pop(key);HANDLES[key]=env
    with env.begin() as tx: payload=tx.get(f"{int(row['real_index']):09d}".encode())
    if payload is None or hashlib.sha256(payload).hexdigest()!=row['record_payload_sha256']:
        raise ValueError('ACTUAL_RECORD_MANIFEST_MISMATCH')
    raw=pickle.loads(payload)
    if len(plain(field(raw,'x')))!=int(row['total_atoms']): raise ValueError('ACTUAL_RECORD_MANIFEST_MISMATCH')
    return raw

def graph(raw):
    from rdkit import Chem
    z=plain(field(raw,'x')).reshape(-1).astype(int)+1
    charge=field(raw,'rdkit_node_formal_charge');idx=field(raw,'rdkit_bond_index');order=field(raw,'rdkit_bond_order')
    if any(v is None for v in (charge,idx,order)): raise ValueError('SOURCE_GRAPH_MISSING')
    charges=plain(charge).reshape(-1);indices=plain(idx);orders=plain(order).reshape(-1)
    if indices.shape!=(2,len(orders)) or len(charges)!=len(z): raise ValueError('SOURCE_GRAPH_SHAPE')
    rw=Chem.RWMol()
    for atomic,c in zip(z,charges):
        atom=Chem.Atom(int(atomic));atom.SetFormalCharge(int(c));atom.SetNoImplicit(True);rw.AddAtom(atom)
    types={1:Chem.BondType.SINGLE,2:Chem.BondType.DOUBLE,3:Chem.BondType.TRIPLE,4:Chem.BondType.AROMATIC}
    seen=set()
    for (i,j),o in zip(indices.T,orders):
        pair=tuple(sorted((int(i),int(j))))
        if pair in seen: continue
        if int(o) not in types:raise ValueError('SOURCE_BOND_TYPE_UNRESOLVED')
        seen.add(pair);rw.AddBond(int(i),int(j),types[int(o)])
        if int(o)==4:
            rw.GetAtomWithIdx(int(i)).SetIsAromatic(True);rw.GetAtomWithIdx(int(j)).SetIsAromatic(True)
    mol=rw.GetMol();Chem.SanitizeMol(mol)
    coords=plain(field(raw,'pos')).astype(np.float64)
    if coords.shape!=(len(z),3) or not np.isfinite(coords).all(): raise ValueError('SOURCE_GEOMETRY_INVALID')
    conf=Chem.Conformer(len(z))
    for i,p in enumerate(coords):conf.SetAtomPosition(i,p.tolist())
    conf.Set3D(True);mol.AddConformer(conf,assignId=True)
    return mol,z,coords

def canonical(m):
    from rdkit import Chem
    return Chem.MolToSmiles(Chem.RemoveHs(Chem.Mol(m)),canonical=True,isomericSmiles=False)

def ordered_graph(m):
    return ([ (a.GetAtomicNum(),a.GetFormalCharge()) for a in m.GetAtoms()],sorted((min(b.GetBeginAtomIdx(),b.GetEndAtomIdx()),max(b.GetBeginAtomIdx(),b.GetEndAtomIdx()),str(b.GetBondType())) for b in m.GetBonds()))

def double_geometry(mol,bond,conf_id,refs=None):
    from rdkit import Chem
    i,j=bond.GetBeginAtomIdx(),bond.GetEndAtomIdx()
    if refs is None:
        left=sorted(a.GetIdx() for a in mol.GetAtomWithIdx(i).GetNeighbors() if a.GetIdx()!=j)
        right=sorted(a.GetIdx() for a in mol.GetAtomWithIdx(j).GetNeighbors() if a.GetIdx()!=i)
        if not left or not right:raise ValueError('PM7_STEREO_UNRESOLVED:double_no_substituent')
        refs=(left[0],right[0])
    xyz=np.asarray(mol.GetConformer(conf_id).GetPositions())
    axis=xyz[j]-xyz[i];axis/=np.linalg.norm(axis)
    u=xyz[refs[0]]-xyz[i];v=xyz[refs[1]]-xyz[j]
    u=u-axis*np.dot(u,axis);v=v-axis*np.dot(v,axis)
    norm=np.linalg.norm(u)*np.linalg.norm(v)
    if norm<1e-8:raise ValueError('PM7_STEREO_UNRESOLVED:collinear_double_substituent')
    cosine=float(np.dot(u,v)/norm)
    if abs(cosine)<1e-8:raise ValueError('PM7_STEREO_UNRESOLVED:orthogonal_double_substituent')
    return tuple(refs),Chem.BondStereo.STEREOCIS if cosine>0 else Chem.BondStereo.STEREOTRANS

def stereo_scope(mol,info):
    from rdkit import Chem
    if str(info.type)=='Atom_Tetrahedral':return True
    if str(info.type)=='Bond_Double':
        bond=mol.GetBondWithIdx(info.centeredOn)
        # Cumulated SP double bonds (e.g. an azide) do not define an E/Z alkene.
        return all(a.GetHybridization()!=Chem.HybridizationType.SP for a in [bond.GetBeginAtom(),bond.GetEndAtom()])
    return False

def geometric_tetra_tag(mol,index,conf_id):
    from rdkit import Chem
    atom=mol.GetAtomWithIdx(index);neighbors=[a.GetIdx() for a in atom.GetNeighbors()]
    if len(neighbors) not in (3,4):return Chem.ChiralType.CHI_UNSPECIFIED
    xyz=np.asarray(mol.GetConformer(conf_id).GetPositions());vectors=xyz[neighbors]-xyz[index]
    volume=float(np.dot(vectors[0],np.cross(vectors[1],vectors[2])))
    if abs(volume)<=.1 and len(neighbors)==4:
        volume=-float(np.dot(vectors[0],np.cross(vectors[1],vectors[3])))
    if volume<-.1:return Chem.ChiralType.CHI_TETRAHEDRAL_CW
    if volume>.1:return Chem.ChiralType.CHI_TETRAHEDRAL_CCW
    return Chem.ChiralType.CHI_UNSPECIFIED

def check_geometry_stereo(mol,conf_id):
    from rdkit import Chem
    geom=Chem.Mol(mol);Chem.AssignAtomChiralTagsFromStructure(geom,confId=conf_id,replaceExistingTags=True)
    for atom in mol.GetAtoms():
        if atom.GetChiralTag()==Chem.ChiralType.CHI_UNSPECIFIED:continue
        observed=geom.GetAtomWithIdx(atom.GetIdx()).GetChiralTag()
        if observed==Chem.ChiralType.CHI_UNSPECIFIED and atom.GetDegree()==3:
            observed=geometric_tetra_tag(mol,atom.GetIdx(),conf_id)
        if observed!=atom.GetChiralTag():return False
    for bond in mol.GetBonds():
        stereo=bond.GetStereo()
        if stereo not in (Chem.BondStereo.STEREOE,Chem.BondStereo.STEREOZ,Chem.BondStereo.STEREOCIS,Chem.BondStereo.STEREOTRANS):continue
        try:_,observed=double_geometry(mol,bond,conf_id,tuple(bond.GetStereoAtoms()))
        except ValueError:return False
        expected=Chem.BondStereo.STEREOCIS if stereo in (Chem.BondStereo.STEREOZ,Chem.BondStereo.STEREOCIS) else Chem.BondStereo.STEREOTRANS
        if observed!=expected:return False
    return True

def fix_stereo(mol,smiles):
    from rdkit import Chem
    template=Chem.MolFromSmiles(smiles)
    if template is None or canonical(mol)!=canonical(template):raise ValueError('SOURCE_SMILES_GRAPH_MISMATCH')
    query=Chem.AddHs(template)
    # Mapping the stored SMILES graph does not renumber the source molecule.
    match=mol.GetSubstructMatch(query,useChirality=False)
    if len(match)!=mol.GetNumAtoms() or len(match)!=query.GetNumAtoms():raise ValueError('SOURCE_SMILES_ATOM_MAPPING_FAILED')
    Chem.AssignStereochemistry(query,cleanIt=True,force=True)
    explicit_target_atoms={match[a.GetIdx()] for a in query.GetAtoms() if a.GetChiralTag()!=Chem.ChiralType.CHI_UNSPECIFIED}
    explicit_target_bonds={mol.GetBondBetweenAtoms(match[b.GetBeginAtomIdx()],match[b.GetEndAtomIdx()]).GetIdx() for b in query.GetBonds() if b.GetStereo() in (Chem.BondStereo.STEREOE,Chem.BondStereo.STEREOZ,Chem.BondStereo.STEREOCIS,Chem.BondStereo.STEREOTRANS)}
    Chem.AssignStereochemistryFrom3D(mol,confId=0,replaceExistingTags=True)
    unfiltered=Chem.Mol(mol);Chem.AssignAtomChiralTagsFromStructure(unfiltered,confId=0,replaceExistingTags=True)
    for info in Chem.FindPotentialStereo(mol):
        if str(info.specified)!='Unspecified' or not stereo_scope(mol,info):continue
        if str(info.type)=='Atom_Tetrahedral' and info.centeredOn in explicit_target_atoms:continue
        if str(info.type)=='Bond_Double' and info.centeredOn in explicit_target_bonds:continue
        if str(info.type)=='Atom_Tetrahedral':
            tag=unfiltered.GetAtomWithIdx(info.centeredOn).GetChiralTag()
            atom=mol.GetAtomWithIdx(info.centeredOn)
            if tag==Chem.ChiralType.CHI_UNSPECIFIED and atom.GetDegree()==3:
                tag=geometric_tetra_tag(mol,info.centeredOn,0)
            atom.SetChiralTag(tag)
        else:
            bond=mol.GetBondWithIdx(info.centeredOn);refs,stereo=double_geometry(mol,bond,0)
            bond.SetStereoAtoms(*refs);bond.SetStereo(stereo)
    explicit_atoms=[];explicit_bonds=[]
    for atom in query.GetAtoms():
        if atom.GetChiralTag()==Chem.ChiralType.CHI_UNSPECIFIED:continue
        target=mol.GetAtomWithIdx(match[atom.GetIdx()])
        query_order=[match[a.GetIdx()] for a in atom.GetNeighbors()]
        target_order=[a.GetIdx() for a in target.GetNeighbors()]
        permutation=[target_order.index(i) for i in query_order]
        inversions=sum(permutation[i]>permutation[j] for i in range(len(permutation)) for j in range(i+1,len(permutation)))
        target.SetChiralTag(atom.GetChiralTag())
        if inversions%2:target.InvertChirality()
        explicit_atoms.append(match[atom.GetIdx()])
    for bond in query.GetBonds():
        if bond.GetStereo() not in (Chem.BondStereo.STEREOE,Chem.BondStereo.STEREOZ,Chem.BondStereo.STEREOCIS,Chem.BondStereo.STEREOTRANS):continue
        i,j=match[bond.GetBeginAtomIdx()],match[bond.GetEndAtomIdx()]
        target=mol.GetBondBetweenAtoms(i,j);refs=[match[x] for x in bond.GetStereoAtoms()]
        if target.GetBeginAtomIdx()!=i:refs.reverse()
        target.SetStereoAtoms(*refs);target.SetStereo(bond.GetStereo());explicit_bonds.append(target.GetIdx())
    Chem.AssignStereochemistry(mol,cleanIt=False,force=True)
    if not mol.GetSubstructMatch(query,useChirality=True):raise ValueError('SMILES_STEREO_UNRESOLVED')
    unresolved=[str(x.type)+':'+str(x.centeredOn) for x in Chem.FindPotentialStereo(mol) if str(x.specified)=='Unspecified' and stereo_scope(mol,x)]
    if unresolved:raise ValueError('PM7_STEREO_UNRESOLVED:'+','.join(unresolved))
    assigned_atoms=[a.GetIdx() for a in mol.GetAtoms() if a.GetChiralTag()!=Chem.ChiralType.CHI_UNSPECIFIED]
    assigned_bonds=[b.GetIdx() for b in mol.GetBonds() if b.GetStereo()!=Chem.BondStereo.STEREONONE]
    pm7=bool(set(assigned_atoms)-set(explicit_atoms) or set(assigned_bonds)-set(explicit_bonds))
    source='SMILES_AND_PM7' if pm7 and (explicit_atoms or explicit_bonds) else 'PM7' if pm7 else 'SMILES'
    return source,Chem.MolToSmiles(Chem.RemoveHs(Chem.Mol(mol)),isomericSmiles=True)

def rmsd(mol,xyz,refxyz):
    # Atom-index correspondence is fixed by the source record, as in all S/S-prime
    # per-atom comparisons. The minimum is over PM7 conformers, not atom renumberings.
    indices=[a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum()!=1]
    if not indices:return 0.0
    x=np.asarray(xyz,dtype=np.float64)[indices];y=np.asarray(refxyz,dtype=np.float64)[indices]
    x=x-x.mean(axis=0);y=y-y.mean(axis=0)
    u,_,vt=np.linalg.svd(x.T@y)
    diagonal=np.eye(3);diagonal[2,2]=1. if np.linalg.det(u@vt)>=0 else -1.
    rotation=u@diagonal@vt
    return float(np.sqrt(np.mean(np.sum((x@rotation-y)**2,axis=1))))

def worker_init():
    import torch
    torch.set_num_threads(1)
    from rdkit import RDLogger
    RDLogger.DisableLog('rdApp.warning');RDLogger.DisableLog('rdApp.error')

def process(task):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from rdkit.Chem import rdtrajectory
    rows,meta=task;mid=meta['molecule_id'];started=time.monotonic()
    seed=int.from_bytes(hashlib.sha256(('sprime-ETKDGv3-v1:'+mid).encode()).digest()[:4],'big')&0x7fffffff
    seed=max(seed,1);n=len(rows)
    summary={'molecule_id':mid,'file_group':int(meta['file_group']),'max_heavy_atoms':int(meta['max_heavy_atoms']),'expected_conformers':n,'generated_conformers':0,'seed':seed,'status':'UNPROCESSED','error':None,'covered_pm7_conformers':0,'stereo_source':None,'stereo_signature':None,'source_record_id':None,'chirality_conflict':any(bool(r.get('QC_molecule_chirality_conflict')) for r in rows),'ez_conflict':any(bool(r.get('QC_molecule_ez_conflict')) for r in rows),'candidate_count':0,'nonconverged_candidates':0,'nonconverged_selected':0,'rejected_stereo_candidates':0,'atom_order_sha256':None,'elapsed_seconds':0.0}
    output=[]
    try:
        raw=[read(r) for r in rows]
        energies=[float(plain(field(d,'energy')).reshape(-1)[0]) if field(d,'energy') is not None else float('inf') for d in raw]
        if not any(np.isfinite(energies)):raise ValueError('PM7_MINIMUM_ENERGY_MISSING')
        lowest=min(range(n),key=lambda i:(energies[i],rows[i]['record_id']))
        mol,z,coords=graph(raw[lowest]);summary['source_record_id']=rows[lowest]['record_id']
        summary['atom_order_sha256']=hashlib.sha256(z.astype('<i8').tobytes()).hexdigest()
        pm7coords=[]
        for d in raw:
            other,otherz,xyz=graph(d)
            if not np.array_equal(z,otherz) or ordered_graph(other)!=ordered_graph(mol):raise ValueError('SOURCE_CONFORMER_GRAPH_OR_ATOM_ORDER_MISMATCH')
            pm7coords.append(xyz)
        source,signature=fix_stereo(mol,str(field(raw[lowest],'smiles')))
        summary['stereo_source']=source;summary['stereo_signature']=signature
        if not AllChem.UFFHasAllMoleculeParams(mol):raise ValueError('UFF_UNSUPPORTED')
        mol.RemoveAllConformers()
        params=AllChem.ETKDGv3();params.randomSeed=seed;params.numThreads=1;params.enforceChirality=True;params.pruneRmsThresh=-1.;params.maxIterations=200
        try:
            ids=list(AllChem.EmbedMultipleConfs(mol,numConfs=3*n,params=params))
        except (ValueError,RuntimeError) as embedding_error:
            ids=[];summary['first_embedding_error']=repr(embedding_error)[:1000]
        retried=not ids
        if retried:
            params.useRandomCoords=True
            try:ids=list(AllChem.EmbedMultipleConfs(mol,numConfs=3*n,params=params))
            except (ValueError,RuntimeError) as embedding_error:raise ValueError('EMBED_FAILED:'+repr(embedding_error)) from embedding_error
        if not ids:raise ValueError('EMBED_FAILED')
        summary['candidate_count']=len(ids)
        candidates=[]
        for cid in ids:
            ff=AllChem.UFFGetMoleculeForceField(mol,confId=cid)
            # Native BFGS trajectory gives actual optimizer iteration snapshots.
            code,trajectory=ff.MinimizeTrajectory(snapshotFreq=1,maxIts=2000,energyTol=1e-6,forceTol=1e-4)
            xyz=np.asarray(mol.GetConformer(cid).GetPositions(),dtype=np.float64)
            energy=float(ff.CalcEnergy())
            if not np.isfinite(xyz).all() or not np.isfinite(energy):raise ValueError('UFF_NONFINITE')
            # Verify the generated/optimized conformer has exactly the fixed stereo signature.
            if not check_geometry_stereo(mol,cid):
                summary['rejected_stereo_candidates']+=1;continue
            candidates.append((energy,cid,xyz,int(code),len(trajectory)))
        if not candidates:raise ValueError('GENERATED_STEREO_MISMATCH')
        summary['nonconverged_candidates']=sum(c[3]!=0 for c in candidates)
        selected=[]
        for candidate in sorted(candidates,key=lambda c:(c[0],c[1])):
            if any(rmsd(mol,candidate[2],old[2])<.5 for old in selected):continue
            selected.append(candidate)
            if len(selected)==n:break
        covered=set()
        for index,(energy,cid,xyz,code,snapshots) in enumerate(selected):
            distances=[rmsd(mol,xyz,p) for p in pm7coords]
            covered.update(i for i,value in enumerate(distances) if value<.5)
            output.append({'molecule_id':mid,'sprime_conf_idx':index,'coordinates':xyz.tolist(),'uff_energy_kcal_mol':energy,'converged':code==0,'iterations':snapshots,'trajectory_snapshots':snapshots,'iteration_limit':2000,'seed':seed,'stereo_source':source,'stereo_signature':signature,'nearest_pm7_rmsd_A':min(distances),'nearest_pm7_record_id':rows[int(np.argmin(distances))]['record_id'],'pm7_rmsds_A':distances,'source_record_id':rows[lowest]['record_id'],'atom_order_sha256':summary['atom_order_sha256'],'embed_random_coords_retry':retried,'status':'SUCCESS' if code==0 else 'UFF_NOT_CONVERGED'})
        summary.update(generated_conformers=len(output),covered_pm7_conformers=len(covered),nonconverged_selected=sum(not x['converged'] for x in output),status='SUCCESS' if len(output)==n else 'INSUFFICIENT_UNIQUE_CONFORMERS')
        if summary['nonconverged_selected']:summary['status']='UFF_NOT_CONVERGED'
    except Exception as exc:
        summary['status']=str(exc).split(':')[0] if isinstance(exc,ValueError) else 'IMPLEMENTATION_ERROR'
        summary['error']=repr(exc)[:2000]
    summary['elapsed_seconds']=time.monotonic()-started
    return summary,output

def main():
    import pyarrow as pa,pyarrow.parquet as pq
    ap=argparse.ArgumentParser();ap.add_argument('--group',type=int,required=True);ap.add_argument('--workers',type=int,required=True);ap.add_argument('--stage',default='pilot');ap.add_argument('--limit',type=int);args=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and 16<=args.workers<=int(os.environ['SLURM_CPUS_PER_TASK'])
    prepared=ROOT/'prepared';out=ROOT/args.stage;out.mkdir(exist_ok=True,parents=True)
    assert (prepared/'population_binding.json').exists()
    metas=pq.read_table(prepared/'pilot_molecules.parquet',filters=[('file_group','=',args.group)]).to_pylist()
    if args.limit:metas=metas[:args.limit]
    keep=['record_id','molecule_id','source_path','real_index','record_payload_sha256','total_atoms','energy_raw','smiles','QC_molecule_chirality_conflict','QC_molecule_ez_conflict']
    rows=pq.read_table(prepared/'pilot_records.parquet',columns=keep,filters=[('file_group','=',args.group)]).to_pylist()
    indexed={m['molecule_id']:[] for m in metas}
    for r in rows:
        if r['molecule_id'] in indexed:indexed[r['molecule_id']].append(r)
    tasks=[(indexed[m['molecule_id']],m) for m in metas]
    started=time.monotonic();summaries=[];conformers=[]
    for target in [out/f'molecules_group{args.group}.parquet',out/f'conformers_group{args.group}.parquet']:
        if target.exists():raise FileExistsError(target)
    with cf.ProcessPoolExecutor(max_workers=args.workers,mp_context=mp.get_context('spawn'),initializer=worker_init) as pool:
        futures={pool.submit(process,t):t[1]['molecule_id'] for t in tasks}
        for f in cf.as_completed(futures):
            summary,confs=f.result();summaries.append(summary);conformers.extend(confs)
            if len(summaries)%100==0:
                save(out/f'progress_group{args.group}.json',{'job_id':os.environ['SLURM_JOB_ID'],'completed':len(summaries),'total':len(tasks),'elapsed_seconds':time.monotonic()-started,'conformers':len(conformers),'status_counts':{k:sum(s['status']==k for s in summaries) for k in set(s['status'] for s in summaries)}})
    summaries.sort(key=lambda s:s['molecule_id']);conformers.sort(key=lambda c:(c['molecule_id'],c['sprime_conf_idx']))
    for name,data in [('molecules',summaries),('conformers',conformers)]:
        path=out/f'{name}_group{args.group}.parquet'
        if data:
            table=pa.Table.from_pylist(data)
            if name=='conformers':table=table.set_column(table.schema.get_field_index('coordinates'),'coordinates',pa.array([d['coordinates'] for d in data],type=pa.list_(pa.list_(pa.float64(),3))))
            pq.write_table(table,str(path)+'.pending',compression='zstd',row_group_size=4096);Path(str(path)+'.pending').replace(path)
        else:
            schema=pa.schema([('molecule_id',pa.string()),('sprime_conf_idx',pa.int64()),('status',pa.string())])
            pq.write_table(pa.Table.from_pylist([],schema=schema),path,compression='zstd')
    from rdkit import rdBase
    save(out/f'receipt_group{args.group}.json',{'job_id':os.environ['SLURM_JOB_ID'],'group':args.group,'molecules':len(summaries),'conformers':len(conformers),'wall_seconds':time.monotonic()-started,'workers':args.workers,'science_cpu_seconds':sum(s['elapsed_seconds'] for s in summaries),'source_sha256':sha(__file__),'rdkit_version':rdBase.rdkitVersion,'embedding_max_attempts_per_conformer':200,'uff_max_iterations':2000,'uff_force_tol':1e-4,'uff_energy_tol':1e-6,'rmsd_mapping':'source_atom_index_heavy_atoms','alignment':'proper_rotation_Kabsch','iterations_evidence':'https://github.com/rdkit/rdkit/blob/Release_2025_09_5/Code/Numerics/Optimizer/BFGSOpt.h','references':[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in [out/f'molecules_group{args.group}.parquet',out/f'conformers_group{args.group}.parquet']]})

if __name__=='__main__':main()
