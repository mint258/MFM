"""New graph/input seam;original scientific objects and native optimizer unchanged."""
import hashlib,importlib,importlib.util,math,os,pathlib,sys,time,traceback,types
from . import contract as C
Q=C.Q;K={}
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
def load():
    global K
    if K:return K
    from workflows.data_v1_final.conformers import common,selection
    recipe=C.meta(Q.pin(C.RECIPE));pins=recipe['science_source_pins'];sys.path.insert(0,str(pathlib.Path(common.__file__).parent))
    try:
        old=sys.modules.get('common');Q.need(old is None or pathlib.Path(old.__file__).absolute()==pathlib.Path(common.__file__).absolute(),'NO_FOREIGN_TOPLEVEL_COMMON_BINDING')
        prior=sys.modules.get('prepare');Q.need(prior is None or pathlib.Path(prior.__file__).absolute()==pathlib.Path(pins[1]['path']),'NO_FOREIGN_LEGACY_PREPARE_BINDING')
        seed_module=module('_no_pm7_original_seed_science',C.catalog_paths()['seed_science']);science=common.load_science(recipe)
    finally:sys.path.pop(0)
    Q.need(pathlib.Path(sys.modules['prepare'].__file__).absolute()==pathlib.Path(pins[1]['path']),'ORIGINAL_PINNED_PREPARE_IMPORT_ONLY')
    from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4.core import _embedding
    # Load the unmodified two original files in a new package namespace. This
    # avoids executing dataset/__init__ and importing unrelated LMDB builders;
    # no existing module or scientific function is replaced or monkeypatched.
    package='_no_pm7_original_descriptor_sources'
    if package not in sys.modules:
        isolated=types.ModuleType(package);isolated.__path__=[str(C.catalog_paths()['generator'].parent)]
        isolated.__package__=package;isolated.__spec__=importlib.util.spec_from_loader(package,loader=None,is_package=True);sys.modules[package]=isolated
    generator=importlib.import_module(package+'.rdkit_descriptor_generator')
    wire=module('_no_pm7_original_corrected_base',C.WIRE);metadata=wire.metadata()
    from workflows.data_v1_final.labels.common import D20_NAMES
    from rdkit import rdBase
    Q.need(rdBase.rdkitVersion=='2025.09.5' and list(wire.D20)==D20_NAMES,'ORIGINAL_RDKIT_AND20_NAMES_WITHOUT_KAPPA')
    by={n:fn for n,fn,mode in generator.GRAPH_DESCRIPTOR_SPECS if mode=='2d'};Q.need(set(D20_NAMES)<=set(by),'ORIGINAL_D20_FUNCTION_OBJECTS')
    science.worker_init()
    import torch
    if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
    K={'science':science,'seed_for':seed_module.seed_for,'selection':selection,'embedding':_embedding,'wire':wire,'D20':D20_NAMES,'functions':by,'metadata':metadata}
    return K
def graph(smiles):
    from rdkit import Chem
    k=load();template=Chem.MolFromSmiles(smiles)
    Q.need(template is not None,'SOURCE_SMILES_GRAPH_UNAVAILABLE_NO_REPAIR')
    mol=Chem.AddHs(template)
    unresolved=[{'type':str(i.type),'center':int(i.centeredOn),'specified':str(i.specified)} for i in Chem.FindPotentialStereo(mol)
        if str(i.specified)!='Specified' and k['science'].stereo_scope(mol,i)]
    return template,mol,unresolved
def d20(template):
    import torch
    k=load();values=[];mask=[];issues=[]
    for name in k['D20']:
        try:
            v=float(k['functions'][name](template));ok=math.isfinite(v)
            if not ok:issues.append(name+':NONFINITE')
        except Exception as exc:v=float('nan');ok=False;issues.append(name+':'+repr(exc))
        values.append(v);mask.append(ok)
    shell=torch.full((len(k['wire'].GRAPH_NAMES),),float('nan'),dtype=torch.float64);flags=torch.zeros(len(shell),dtype=torch.bool)
    for name,v,ok in zip(k['D20'],values,mask):i=k['wire'].GRAPH_NAMES.index(name);shell[i]=v;flags[i]=ok
    return {'names':k['D20'],'values':values,'valid_mask':mask,'issues':issues},shell,flags
def descriptors(source,template,mol,z,xyz,shell,flags):
    import numpy as np,torch
    k=load();edges=[(b.GetBeginAtomIdx(),b.GetEndAtomIdx()) for b in mol.GetBonds()];indices=np.asarray(edges,dtype=np.int64).reshape(-1,2).T
    raw={'smiles':source['isomeric_smiles'],'x':torch.tensor(z-1,dtype=torch.int64),'pos':torch.tensor(xyz,dtype=torch.float64),
        'rdkit_graph_desc':shell,'rdkit_graph_desc_mask':flags,'rdkit_bond_index':torch.tensor(indices,dtype=torch.int64),
        'geometry_context':'NEW_UFF_NO_PM7_INPUT','energy':None}
    output,issues=k['wire'].corrected_base(raw,{'smiles':source['isomeric_smiles']})
    Q.need(output['rdkit_graph_desc'].dtype==torch.float64,'NO_FLOAT32_DESCRIPTOR_STAGING')
    value=output['D_native_3D'];value['PBF_A']=value.pop('PBF');value['SASA_atom_A2']=None if value['SASA_atom_A2'] is None else value['SASA_atom_A2'].tolist()
    return value,issues,{'names':k['D20'],'values':output['rdkit_graph_desc'].tolist(),'valid_mask':output['rdkit_graph_desc_mask'].tolist(),'issues':[]}
def distinct_selected(chosen,z):
    import numpy as np
    distinct=[];seen={};aliases=[]
    for row in chosen:
        xyz=np.asarray(row['coordinates'],dtype='<f8');geom=C.sha(np.asarray(z,dtype='<i8').tobytes()+xyz.tobytes())
        if geom in seen:aliases.append({'candidate_id':row['candidate_id'],'same_geometry_as_candidate_id':seen[geom],'geometry_sha256':geom})
        else:seen[geom]=row['candidate_id'];distinct.append(row)
    return distinct,aliases
def process(source,journal,event,compat=False,checkpoint=lambda:None):
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import AllChem,rdtrajectory
    k=load();start=time.monotonic();cpu=time.process_time();mid=C.new_mid(source['pubchem_version'],source['cid'],source['full_key']);seed=k['seed_for'](mid,False)
    result={'molecule_id':mid,'source':source,'dataset_version':'v2_candidate','training_eligible':False,'geometry_source':'uff_sprime',
        'PM7_pointer':None,'PM7_HOF':None,'PM7_stereo_reference':None,'PM7_RMSD':None,'seed':seed,'order_seed':C.SEED,'conformers':[],
        'D20':None,'orders':{},'state':'UNKNOWN','candidate_pool_goal':100,'candidate_requested':0,'candidate_embedded':0,'embedding_calls':0,
        'candidate_converged_stereo_valid':0,'optimizer_attempted':0,'optimizer_returned':0,'error':None}
    try:
        template,mol,unresolved=graph(source['isomeric_smiles']);Q.need(Chem.MolToInchiKey(template)==source['full_key'],'FROZEN_GRAPH_FULLKEY_MISMATCH_NO_ALIAS_REPAIR')
        result['D20'],shell,flags=d20(template);result['unassigned_stereo']=unresolved
        z=np.asarray([a.GetAtomicNum() for a in mol.GetAtoms()],dtype='<i8');result['atomic_numbers']=z.tolist();result['atom_order_sha256']=C.sha(z.tobytes())
        if unresolved:result['state']='STEREO_REFERENCE_UNAVAILABLE_NO_PM7';return result
        Q.need(AllChem.UFFHasAllMoleculeParams(mol),'UFF_UNSUPPORTED_TECHNICAL_UNKNOWN_NOT_NEW_CHEMICAL_EXCLUSION')
        checkpoint();Q.need(not event.is_set(),'RESOURCE_STOP_BEFORE_EMBEDDING_NO_RETRY')
        original_graph=k['science'].ordered_graph(mol);attempts=__import__(__package__+'.io',fromlist=['Embedding']).Embedding(journal)
        result['candidate_requested']=100
        try:ids=k['embedding'](mol,AllChem,100,seed,attempts)
        finally:attempts.flush_last();result['embedding_calls']=attempts.index;result['requested_sum_including_original_zero_fallback']=100*attempts.index
        result['candidate_embedded']=len(ids);valid=[]
        for cid in ids:
            checkpoint()
            if event.is_set():raise RuntimeError('RESOURCE_STOP_BEFORE_NEXT_NATIVE_CANDIDATE_PARTIAL_NO_RETRY')
            entry={'phase':'optimizer_intent','candidate_id':int(cid),'seed':seed,'maxIts':2000,'energyTol':1e-6,'forceTol':1e-4,'snapshotFreq':1};journal.write(entry)
            field=AllChem.UFFGetMoleculeForceField(mol,confId=cid);Q.need(field is not None,'ORIGINAL_UFF_FORCEFIELD_UNAVAILABLE')
            result['optimizer_attempted']+=1;code,trajectory=field.MinimizeTrajectory(snapshotFreq=1,maxIts=2000,energyTol=1e-6,forceTol=1e-4)
            result['optimizer_returned']+=1;xyz=np.asarray(mol.GetConformer(cid).GetPositions(),dtype='<f8');energy=float(field.CalcEnergy())
            finite=bool(np.isfinite(xyz).all() and math.isfinite(energy));stereo=finite and k['science'].check_geometry_stereo(mol,cid)
            Q.need(k['science'].ordered_graph(mol)==original_graph and [a.GetAtomicNum() for a in mol.GetAtoms()]==z.tolist(),'GENERATED_GRAPH_OR_ATOM_ORDER_CHANGED')
            row={'candidate_key':'generated:%06d'%cid,'candidate_id':int(cid),'coordinates':xyz.tolist(),'energy':energy,'seed':seed,'iterations':len(trajectory),
                'optimizer_code':int(code),'stereo_valid':bool(stereo),'finite':finite,'origin':'new_pubchem_original_10N'}
            journal.write({'phase':'optimizer_return','candidate':row})
            if finite and stereo and code==0:valid.append(row)
        distance=lambda a,b:k['science'].rmsd(mol,a['coordinates'],b['coordinates'])
        chosen=k['selection'].select_fill([],valid,10,distance,0.5)
        checkpoint()
        result['candidate_converged_stereo_valid']=len(valid);result['original_selection_candidate_ids']=[r['candidate_id'] for r in chosen];distinct,aliases=distinct_selected(chosen,z)
        for row in distinct:
            xyz=np.asarray(row['coordinates'],dtype='<f8');i=len(result['conformers']);value,issues,wire_D20=descriptors(source,template,mol,z,xyz,shell,flags)
            Q.need(np.asarray(wire_D20['values'],dtype='<f8').tobytes()==np.asarray(result['D20']['values'],dtype='<f8').tobytes(),'ORIGINAL_WIRE_D20_EQUALS_ORIGINAL_DIRECT_FUNCTION_BITS')
            wire_D20['issues']=result['D20']['issues']
            result['D20']=wire_D20
            conf={**row,'conformer_id':i,'geometry_sha256':C.sha(z.tobytes()+xyz.tobytes()),'coordinate_sha256':C.sha(xyz.tobytes()),'D3':value,'D3_issues':issues}
            result['conformers'].append(conf)
        order_rows=[{**r,'energy':r['energy']} for r in result['conformers']]
        result['orders']=k['selection'].conformer_orders(order_rows,distance,mid,'uff_sprime',C.SEED)
        result['exact_native_geometry_aliases']=aliases
        result['state']='SUCCESS' if len(result['conformers'])==10 else 'EXACT_DUPLICATE_GEOMETRY_UNKNOWN' if aliases else 'INSUFFICIENT_CONVERGED_CANDIDATES'
        result['compatibility']=compatibility(source,template,mol,z,shell,flags,result) if compat else None
    except BaseException as exc:
        result['state']='TECHNICAL_UNKNOWN';result['error']=repr(exc);result['traceback']=traceback.format_exc()
        fatal=any(s in str(exc) for s in ('FROZEN_GRAPH_FULLKEY_MISMATCH','GENERATED_GRAPH_OR_ATOM_ORDER_CHANGED','ORIGINAL_WIRE_D20_EQUALS'))
        result['source_or_descriptor_contract_HOLD']=fatal
        if fatal:event.set()
    finally:
        result['elapsed_seconds']=time.monotonic()-start;result['worker_cpu_seconds']=time.process_time()-cpu
        result['audit_sample']=int(hashlib.sha256(('data-v1-audit:'+mid).encode()).hexdigest(),16)%100==0
        result['no_new_QM_calls']=True
    return result
def compatibility(source,template,mol,z,shell,flags,result):
    """Independent direct D3 API path checks the new raw-wire seam,not old PM7 process parity."""
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import AllChem,Descriptors3D,rdFreeSASA
    checks=[]
    for row in result['conformers']:
        direct=Chem.Mol(mol);direct.RemoveAllConformers();c=Chem.Conformer(len(z))
        for i,point in enumerate(row['coordinates']):c.SetAtomPosition(i,point)
        c.Set3D(True);direct.AddConformer(c)
        d={n:float(getattr(Descriptors3D,n)(direct)) for n in ('PMI1','PMI2','PMI3')};d['PBF_A']=float(Descriptors3D.PBF(direct));d['volume_A3']=float(AllChem.ComputeMolVolume(direct,gridSpacing=.2,boxMargin=2.0))
        radii=[Chem.GetPeriodicTable().GetRvdw(int(n)) for n in z];opts=rdFreeSASA.SASAOpts(rdFreeSASA.SASAAlgorithm.LeeRichards,rdFreeSASA.SASAClassifier.Protor,1.4)
        d['SASA_total_A2']=float(rdFreeSASA.CalcSASA(direct,radii,opts=opts));d['SASA_atom_A2']=[float(a.GetProp('SASA')) for a in direct.GetAtoms()]
        checks.append(all(np.asarray(d[n],dtype='<f8').tobytes()==np.asarray(row['D3'][n],dtype='<f8').tobytes() for n in d))
    return {'direct_original_D3_functions_vs_original_corrected_base_bits_equal':bool(checks) and all(checks),'conformers_checked':len(checks),
        'original_PM7_dependent_process_task_equivalence_claimed':False}
