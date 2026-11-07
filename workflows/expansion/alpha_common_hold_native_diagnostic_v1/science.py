"""Independent native stage probes; every candidate remains diagnostic-only."""
import ast
import hashlib
import inspect
import os
from pathlib import Path
import traceback

MURCKO_SHA='0cd0329a7cfa981f9cf6cce7a015e1ef78e5c513238a18dc7962c641eb516464'
MURCKO_BLOB='8b456b1d3ae6fcdce6b1e0e13239ff382af9efe9'
MURCKO_URL='https://github.com/rdkit/rdkit/blob/Release_2025_09_5/rdkit/Chem/Scaffolds/MurckoScaffold.py'
ENV=None


def generic_before_remove_hs(Chem,mol):
    res = Chem.Mol(mol)
    for atom in res.GetAtoms():
        if atom.GetAtomicNum() != 1:
            atom.SetAtomicNum(6)
        atom.SetIsAromatic(False)
        atom.SetIsotope(0)
        atom.SetFormalCharge(0)
        atom.SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
        atom.SetNoImplicit(0)
        atom.SetNumExplicitHs(0)
    for bond in res.GetBonds():
        bond.SetBondType(Chem.BondType.SINGLE)
        bond.SetIsAromatic(False)
    return res


def source_proof(Murcko):
    path=Path(inspect.getsourcefile(Murcko.MakeScaffoldGeneric));raw=path.read_bytes()
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if hashlib.sha256(raw).hexdigest()!=MURCKO_SHA or blob!=MURCKO_BLOB:raise ValueError('Exact official RDKit2025.09.5 Murcko source required')
    tree=ast.parse(raw);old=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='MakeScaffoldGeneric')
    current=ast.parse(Path(__file__).read_text());candidate=next(n for n in current.body if isinstance(n,ast.FunctionDef) and n.name=='generic_before_remove_hs')
    body=old.body[1:] if isinstance(old.body[0],ast.Expr) and isinstance(old.body[0].value,ast.Constant) and isinstance(old.body[0].value.value,str) else old.body
    dump=lambda nodes:ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False)
    if dump(body[:-1])!=dump(candidate.body[:-1]):raise ValueError('Diagnostic generic atom/bond conversion differs from official AST')
    expected_return=ast.parse('def f():\n return Chem.RemoveHs(res)').body[0].body[0]
    if ast.dump(body[-1],include_attributes=False)!=ast.dump(expected_return,include_attributes=False):raise ValueError('Exact official RemoveHs return required')
    return dict(installed_source=dict(path=str(path),bytes=len(raw),sha256=MURCKO_SHA),official_git_blob_sha1=blob,
      official_release='Release_2025_09_5',official_url=MURCKO_URL,
      conversion_body_AST_equal=True,conversion_body_AST_sha256=hashlib.sha256(dump(body[:-1]).encode()).hexdigest(),
      original_terminal='Chem.RemoveHs(res)',diagnostic_conversion_returns_before_original_RemoveHs=True,
      adoption_authorized=False)


def capture(fn,serialize=lambda x:x):
    try:
        value=fn();return value,dict(status='PASS',result=serialize(value))
    except Exception as exc:
        return None,dict(status='ERROR',exception_type=type(exc).__name__,message=str(exc),
          exact_traceback=traceback.format_exc(),frames=[dict(file=f.filename,line=f.lineno,function=f.name,source_line=f.line) for f in traceback.extract_tb(exc.__traceback__)])


def atoms(mol):
    return [dict(index=a.GetIdx(),atomic_number=a.GetAtomicNum(),degree=a.GetDegree(),
      heavy_degree=sum(n.GetAtomicNum()!=1 for n in a.GetNeighbors()),formal_charge=a.GetFormalCharge(),
      isotope=a.GetIsotope(),aromatic=a.GetIsAromatic(),explicit_H_count=a.GetNumExplicitHs(),
      no_implicit=a.GetNoImplicit(),chiral_tag=str(a.GetChiralTag())) for a in mol.GetAtoms()]


def topology(mol):
    heavy=[a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum()!=1];pos={x:i for i,x in enumerate(heavy)}
    edges=sorted(sorted((pos[b.GetBeginAtomIdx()],pos[b.GetEndAtomIdx()])) for b in mol.GetBonds() if b.GetBeginAtomIdx() in pos and b.GetEndAtomIdx() in pos)
    return dict(heavy_atoms=len(heavy),retained_heavy_adjacency=edges)


def snapshot(mol):
    return dict(atoms=atoms(mol),topology=topology(mol),
      bonds=[dict(begin=b.GetBeginAtomIdx(),end=b.GetEndAtomIdx(),type=str(b.GetBondType()),aromatic=b.GetIsAromatic()) for b in mol.GetBonds()])


def generic_probe(mol):
    Chem,DataStructs,unusedD,unusedL,unusedR,Murcko,unusedFP=ENV['modules']
    original,official=capture(lambda:Murcko.MakeScaffoldGeneric(Chem.Mol(mol)),lambda m:dict(key=Chem.MolToSmiles(m,isomericSmiles=False),snapshot=snapshot(m)))
    middle=generic_before_remove_hs(Chem,mol)
    _,remove_hs=capture(lambda:Chem.RemoveHs(Chem.Mol(middle)),snapshot)
    _,sanitize=capture(lambda:Chem.SanitizeMol(Chem.Mol(middle)),lambda flag:str(flag))
    deferred,unsanitized=capture(lambda:Chem.RemoveHs(Chem.Mol(middle),sanitize=False),snapshot)
    candidate=dict(status='NOT_AVAILABLE',diagnostic_only=True,adoption_authorized=False)
    if deferred is not None:
        # Recompute only the temporary intermediate's property cache permissively;
        # no chemical sanitization or original graph/descriptor is changed.
        _,cache=capture(lambda:deferred.UpdatePropertyCache(strict=False),lambda _:None)
        key,key_step=capture(lambda:Chem.MolToSmiles(deferred,isomericSmiles=False))
        invariant=(topology(deferred)==topology(mol)
          and all(a.GetAtomicNum()==6 and not a.GetIsAromatic() for a in deferred.GetAtoms())
          and all(b.GetBondType()==Chem.BondType.SINGLE and not b.GetIsAromatic() for b in deferred.GetBonds()))
        candidate=dict(status='PASS' if key_step['status']=='PASS' and invariant else 'UNRESOLVED',
          key=key,key_step=key_step,property_cache_strict_false=cache,snapshot=snapshot(deferred),
          heavy_adjacency_and_allC_SINGLE_invariant=invariant,chemical_sanitization_deferred=True,
          diagnostic_only=True,adoption_authorized=False)
        if not invariant:candidate['topology_constraint_failure']='DIAGNOSTIC_CANDIDATE_INVALID_NO_ADOPTION'
    return dict(source_snapshot=snapshot(mol),official_MakeScaffoldGeneric=official,
      official_conversion_before_RemoveHs_snapshot=snapshot(middle),
      independent_default_RemoveHs=remove_hs,independent_SanitizeMol=sanitize,
      RemoveHs_sanitize_false=unsanitized,diagnostic_deferred_sanitize_candidate=candidate,
      official_and_candidate_keys_exactly_equal=(official['status']=='PASS' and candidate['status']=='PASS'
        and official['result']['key']==candidate['key']))


def initialize(plan,barrier,directory):
    global ENV
    try:
        from ..alpha_runtime_v1 import common as Q
        from ..common_molecular_fp_candidate_v1 import worker as W
        from .. import screen,features_legacy_compatible_v2 as old,features_generic_candidate_v1 as generic
        for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
        kernel,kernel_proof=W.load_kernel();modules=screen.rdkit_modules();Murcko=modules[5]
        proof=source_proof(Murcko)
        declared={r['path']:r for r in plan['code_references']+plan.get('scientific_source_references',[])}
        for path in [Path(__file__),Path(W.__file__),Path(screen.__file__),Path(old.__file__),Path(generic.__file__),Path(proof['installed_source']['path'])]:
            if declared.get(str(path))!=Q.reference(path):raise ValueError('Actual native source must be pinned: '+str(path))
        if old.chemical_flags is not screen.chemical_flags or kernel is not old.features_candidate:raise ValueError('Unchanged original native kernel/chemical flags required')
        ENV=dict(kernel=kernel,modules=modules,screen=screen,generic=generic,source_proof=proof)
        Q.write(Path(directory)/('worker_%s.json'%os.getpid()),dict(uid=os.getuid(),job_id=os.environ['SLURM_JOB_ID'],pid=os.getpid(),
          official_Murcko_source=proof,original_kernel_source_proof=kernel_proof,
          original_kernel_and_chemical_flags_function_objects_unchanged=True,new_chemical_filter=False))
        barrier.wait()
    except BaseException:
        barrier.abort()
        raise


def diagnose(task):
    Chem,DataStructs,Descriptors,Lipinski,rdMolDescriptors,Murcko,Fingerprint=ENV['modules']
    smiles=task['source_smiles'];ordinal=task['ordinal']
    # Original full function is called, never reconstructed or patched.
    unused,whole=capture(lambda:ENV['kernel'](None,smiles,ordinal))
    flags_value,flags_step=capture(lambda:ENV['screen'].chemical_flags(smiles),lambda value:dict(flags=value[1],template_present=value[0] is not None))
    mol,parse=capture(lambda:Chem.MolFromSmiles(smiles.strip()),lambda m:None if m is None else snapshot(m))
    result=dict(task=task,worker_pid=os.getpid(),original_full_features_candidate=whole,
      original_chemical_flags=flags_step,independent_original_template_parse=parse,stages={},ring_fragments=[],
      diagnostic_only=True,adoption_authorized=False,original_kernel_modified=False,Common_reference_emitted=False)
    if mol is None:return result
    def step(name,fn,serialize=lambda x:x):
        value,event=capture(fn,serialize);result['stages'][name]=event;return value
    step('independent_template_full_InChIKey',lambda:Chem.MolToInchiKey(Chem.Mol(mol)))
    step('independent_template_canonical_isomeric_SMILES',lambda:Chem.MolToSmiles(Chem.Mol(mol),isomericSmiles=True))
    step('independent_template_ECFP4_2048',lambda:Fingerprint.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=False).GetFingerprint(Chem.Mol(mol)),lambda fp:DataStructs.BitVectToBinaryText(fp).hex())
    descriptors={
      'molecular_weight_Da':lambda:Descriptors.MolWt(Chem.Mol(mol)),
      'rings':lambda:rdMolDescriptors.CalcNumRings(Chem.Mol(mol)),
      'aromatic_rings':lambda:rdMolDescriptors.CalcNumAromaticRings(Chem.Mol(mol)),
      'rotatable_bonds':lambda:Lipinski.NumRotatableBonds(Chem.Mol(mol)),
      'hbd':lambda:Lipinski.NumHDonors(Chem.Mol(mol)), 'hba':lambda:Lipinski.NumHAcceptors(Chem.Mol(mol)),
      'tpsa_A2':lambda:rdMolDescriptors.CalcTPSA(Chem.Mol(mol)), 'logp':lambda:Descriptors.MolLogP(Chem.Mol(mol)),
      'stereocenters':lambda:len(Chem.FindMolChiralCenters(Chem.Mol(mol),includeUnassigned=True))}
    for name,fn in descriptors.items():step('independent_original_template_descriptor.'+name,fn)
    scaffold=step('original_GetScaffoldForMol',lambda:Murcko.GetScaffoldForMol(Chem.Mol(mol)),snapshot)
    if scaffold is not None:result['whole_Murcko_generic_stages']=generic_probe(scaffold)
    fragments=step('original_cut_ring_fragments',lambda:ENV['generic'].cut_ring_fragments(Chem.Mol(mol)),lambda v:dict(fragment_original_atom_mappings=[list(x) for x in v[1]],removed_non_ring_bonds=v[2]))
    if fragments is not None:
        for index,(fragment,mapping) in enumerate(zip(fragments[0],fragments[1])):
            if not fragment.GetNumBonds():continue
            original_fragment=Chem.Mol(fragment)
            unused,original_sanitize=capture(lambda:Chem.SanitizeMol(original_fragment),lambda flag:str(flag))
            detail=dict(fragment_index=index,original_atom_indices=list(mapping),
              exact_original_fragment_sanitize=original_sanitize,generic_stages_on_uncorrupted_fragment=generic_probe(fragment))
            if original_sanitize['status']=='PASS':
                detail['generic_stages_after_original_fragment_sanitize']=generic_probe(original_fragment)
            result['ring_fragments'].append(detail)
    return result


def worker_ready(index):
    return dict(index=index,pid=os.getpid(),uid=os.getuid(),job_id=os.environ['SLURM_JOB_ID'],
      original_native_sources_loaded=ENV is not None)
