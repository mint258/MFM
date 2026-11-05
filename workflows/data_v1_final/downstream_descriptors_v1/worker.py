"""Target-free existing-structure readers and descriptor worker."""
from __future__ import annotations
import ast
import collections
import csv
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import types

CONFIG={};CANDIDATES={};EXPANSION={};DESCRIPTORS=[];PARSER=None;SCF=None
SDF={};CSV={}


def structure_only_sdf(path):
    """Retain each mol block through M END; never decode SDF properties."""
    result=[];lines=[];structural=True
    with Path(path).open('rb') as stream:
        for line in stream:
            if line.strip()==b'$$$$':
                result.append(b''.join(lines).decode('utf-8',errors='replace'));lines=[];structural=True
            elif structural:
                lines.append(line)
                if re.match(rb'^M\s+END\s*$',line.strip()):structural=False
    if lines:result.append(b''.join(lines).decode('utf-8',errors='replace'))
    return result


def read_xyz(path,units):
    from rdkit import Chem
    factors={'angstrom':1.0,'bohr':0.529177210903}
    if units not in factors:raise ValueError('EXPLICIT_XYZ_COORDINATE_UNIT_REQUIRED')
    z=[];xyz=[]
    with Path(path).open(encoding='utf-8') as stream:
        n=int(stream.readline().strip());stream.readline()  # comment/targets deliberately ignored
        for _ in range(n):
            cells=stream.readline().split()
            if len(cells)<4:raise ValueError('XYZ_ATOM_ROW_MISSING')
            atomic=int(Chem.GetPeriodicTable().GetAtomicNumber(cells[0]))
            values=[float(value.replace('*^','e'))*factors[units] for value in cells[1:4]]
            if atomic<1 or not all(math.isfinite(value) for value in values):raise ValueError('XYZ_ATOM_ROW_INVALID')
            z.append(atomic);xyz.append(values)
        # The only additional QM9 structure field is the original GDB SMILES.
        # Its vibrational-frequency/target line is skipped without parsing.
        smiles=None
        if 'qm9' in str(path).lower() or Path(path).name.startswith('dsgdb9nsd_'):
            stream.readline()
            fields=stream.readline().split()
            if fields:smiles=fields[0]
    return z,xyz,smiles


def scalar_smiles_from_span(frame):
    start,end=frame['smiles_physical_span']
    path=frame['source_file']['path']
    with Path(path).open('rb') as stream:
        stream.seek(start);token=stream.read(end-start).decode('utf-8')
    values=next(csv.reader(io.StringIO(token)))
    if len(values)!=1:raise ValueError('SMILES_PHYSICAL_SPAN_NOT_ONE_CSV_FIELD')
    return values[0]


def csv_structure_smiles(frame):
    import pyarrow as pa
    import pyarrow.csv as pcsv
    path=frame['source_file']['path']
    if path not in CSV:
        with Path(path).open(encoding='utf-8-sig',newline='') as stream:header=next(csv.reader(stream))
        names=[name for name in header if name.lower() in ('smiles','canonical_smiles','isomeric_smiles')]
        if len(names)!=1:raise ValueError('UNIQUE_EXISTING_SMILES_COLUMN_REQUIRED')
        name=names[0]
        table=pcsv.read_csv(path,convert_options=pcsv.ConvertOptions(include_columns=[name],column_types={name:pa.string()}))
        CSV[path]=table.column(name).to_pylist()
    index=int(frame['source_record_1based'])-1
    if not 0<=index<len(CSV[path]):raise ValueError('ORIGINAL_STRUCTURAL_ROW_ORDINAL_INVALID')
    return CSV[path][index]


def source_structure(member):
    """Return existing graph and existing coordinates; never infer/generate graph."""
    from rdkit import Chem
    dataset=member['dataset'];frame=member['source_frame'];artifact=member.get('geometry_artifact_ref',{})
    mol=None;smiles=None;z=None;coords=None;reason=None;record_id=frame.get('record_id',member['member_uid'])
    if dataset in ('qm7','qm9'):
        z,coords,smiles=read_xyz(frame['path'],frame['source_units'])
        if dataset=='qm9' and smiles:mol=Chem.MolFromSmiles(smiles)
        if dataset=='qm7':reason='QM7_AUTHOR_GRAPH_CHARGE_AND_SPIN_UNDETERMINED'
    elif dataset=='cyp_isoform':
        path=frame['source_file']['path']
        if path not in SDF:SDF[path]=structure_only_sdf(path)
        mol=Chem.MolFromMolBlock(SDF[path][int(frame['source_record_1based'])-1],sanitize=True,removeHs=False,strictParsing=True)
        if mol is None:raise ValueError('EXISTING_CYP_SOURCE_GRAPH_INVALID')
        z=[atom.GetAtomicNum() for atom in mol.GetAtoms()]
        if artifact.get('kind')=='original_source_3d' and artifact.get('status')=='GEOMETRY_READY':
            if mol.GetNumConformers()!=1 or not mol.GetConformer().Is3D():raise ValueError('DECLARED_ORIGINAL_3D_NOT_PRESENT')
            coords=mol.GetConformer().GetPositions().tolist()
        else:
            candidate=CANDIDATES.get(record_id)
            if candidate and candidate.get('status')=='GENERATED_CANDIDATE_READY':
                if candidate['native_atomic_numbers']!=z:raise ValueError('SAVED_CANDIDATE_NATIVE_ATOM_ORDER_CHANGED')
                coords=candidate['generated_native_coordinates_float64']
            else:reason='EXISTING_GEOMETRY_NOT_READY'
    elif dataset=='az_exactsom':
        smiles=csv_structure_smiles(frame);mol=Chem.MolFromSmiles(smiles)
        if mol is None:raise ValueError('EXISTING_AZ_SOURCE_SMILES_INVALID')
        z=[atom.GetAtomicNum() for atom in mol.GetAtoms()]
        candidate=CANDIDATES.get(record_id)
        if candidate and candidate.get('status')=='GENERATED_CANDIDATE_READY':
            if candidate['native_atomic_numbers']!=z:raise ValueError('SAVED_AZ_CANDIDATE_NATIVE_ATOM_ORDER_CHANGED')
            coords=candidate['generated_native_coordinates_float64']
        else:reason='EXISTING_GEOMETRY_NOT_READY'
    elif dataset=='expansionrx':
        smiles=scalar_smiles_from_span(frame);mol=Chem.MolFromSmiles(smiles)
        if mol is None:raise ValueError('EXISTING_EXPANSION_SOURCE_SMILES_INVALID')
        z=[atom.GetAtomicNum() for atom in mol.GetAtoms()]
        candidate=EXPANSION.get(member['member_uid'])
        if candidate and candidate.get('native_coordinates_float64') is not None:
            encoded=candidate['native_x'];observed=[int(value[0] if isinstance(value,list) else value)+1 for value in encoded]
            if observed!=z:raise ValueError('EXISTING_EXPANSION_NATIVE_ATOM_ORDER_CHANGED')
            coords=candidate['native_coordinates_float64']
        else:reason='EXISTING_EXPANSION_GEOMETRY_NOT_READY'
    else:raise ValueError('UNDECLARED_DOWNSTREAM_DATASET')
    if coords is not None and (len(coords)!=len(z) or any(len(row)!=3 or not all(math.isfinite(float(v)) for v in row) for row in coords)):
        raise ValueError('EXISTING_GEOMETRY_ATOM_ALIGNMENT_INVALID')
    return {'mol':mol,'smiles':smiles,'atomic_numbers':z,'coordinates_A':coords,
        'geometry_reason':reason,'record_id':record_id}


def electronic_state(mol,z,coords):
    """Only a known graph with complete existing atomic geometry gets xTB state."""
    from rdkit import Chem
    if mol is None:return None,None,'SOURCE_GRAPH_CHARGE_SPIN_UNDETERMINED'
    if coords is None:return None,None,'EXISTING_GEOMETRY_NOT_READY'
    expected=Chem.AddHs(Chem.Mol(mol))  # graph-only H count; no coordinate generation
    if collections.Counter(atom.GetAtomicNum() for atom in expected.GetAtoms())!=collections.Counter(z):
        return None,None,'SOURCE_GEOMETRY_MISSING_H_COORDINATES_OR_GRAPH_COMPOSITION_MISMATCH'
    charge=int(Chem.GetFormalCharge(mol))
    if any(atom.GetNumRadicalElectrons() for atom in mol.GetAtoms()):
        return charge,None,'SOURCE_SPIN_NOT_EXPLICITLY_CLOSED_SHELL'
    if (sum(z)-charge)%2:return charge,None,'SOURCE_ELECTRON_PARITY_DOES_NOT_SUPPORT_CLOSED_SHELL'
    return charge,0,None


def load_numeric_parser(path):
    """Keep original parser numerics; omit its obsolete source-rehash statement."""
    path=Path(path);tree=ast.parse(path.read_text(encoding='utf-8'));kept=[];removed=0
    for node in tree.body:
        if isinstance(node,ast.If) and 'FROZEN_PARSER_SOURCE_SHA_DIFFERS' in ast.unparse(node):
            removed+=1
        else:kept.append(node)
    if removed!=1:raise ValueError('ONE_LEGACY_PARSER_REHASH_GUARD_EXPECTED')
    module=types.ModuleType('_window2_downstream_wp5_parser');module.__file__=str(path)
    exec(compile(ast.Module(body=kept,type_ignores=[]),str(path),'exec'),module.__dict__)
    return module


def load_scf_parser(path):
    """Original SCC iteration/convergence rules, without output-content hashing."""
    path=Path(path);module=types.ModuleType('_window2_downstream_scf');module.__file__=str(path)
    exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),module.__dict__)
    def texts(files):
        if isinstance(files,dict):files=[{'name':key,'data':value} for key,value in files.items()]
        return {Path(row['name']).name:((row['data'].decode('utf-8',errors='replace') if isinstance(row['data'],bytes) else row['data']),None)
            for row in files if Path(row['name']).name in ('input.out','process.out','input.aux')}
    module._texts=texts
    return module


def descriptor_functions(names=None):
    from rdkit.Chem import Descriptors
    values=dict(Descriptors._descList)
    ordered=sorted(values) if names is None else list(names)
    if len(ordered)!=len(set(ordered)) or any(name not in values for name in ordered):
        raise ValueError('FROZEN_RDKIT_DESCRIPTOR_NAMES_UNAVAILABLE')
    return [(name,values[name]) for name in ordered]


def initialize(config,names):
    global CONFIG,CANDIDATES,EXPANSION,DESCRIPTORS,PARSER,SCF
    CONFIG=config
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    from rdkit import rdBase
    if tuple(map(int,rdBase.rdkitVersion.split('.'))) != tuple(map(int,config['rdkit_version'].split('.'))):
        raise ValueError('EXISTING_RDKIT_VERSION_CHANGED')
    DESCRIPTORS=descriptor_functions(names)
    CANDIDATES={}
    with Path(config['saved_som_candidates']).open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);CANDIDATES[row['record_id']]=row
    inventory=json.loads(Path(config['expansion_geometry']).read_text(encoding='utf-8'))
    EXPANSION={row['member_uid']:row for row in inventory['records']}
    PARSER=load_numeric_parser(config['wp5_parser'])
    SCF=load_scf_parser(config['scf_parser'])


def finite_or_none(value):
    if isinstance(value,float):return value if math.isfinite(value) else None
    if isinstance(value,dict):return {key:finite_or_none(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):return [finite_or_none(item) for item in value]
    return value


def quantum_features(values):
    """Retain raw native atom arrays plus explicit graph-level aggregate features."""
    result={key:values.get(key) for key in ('energy_Eh','homo_eV','lumo_eV')}
    homo,lumo=result['homo_eV'],result['lumo_eV']
    result['gap_eV']=lumo-homo if homo is not None and lumo is not None else None
    dipole=values.get('dipole_Debye')
    result['dipole_norm_Debye']=math.sqrt(sum(v*v for v in dipole)) if dipole and len(dipole)==3 else None
    for field in ('charges_e','D4_atomic_C6_au','D4_atomic_alpha_bohr3'):
        array=values.get(field)
        if array:
            mean=sum(array)/len(array)
            result.update({field+'_sum':sum(array),field+'_mean':mean,field+'_min':min(array),field+'_max':max(array),
                field+'_std':math.sqrt(sum((v-mean)**2 for v in array)/len(array))})
        else:
            result.update({field+'_'+name:None for name in ('sum','mean','min','max','std')})
    return finite_or_none(result)


def xtb(structure,charge,spin,ordinal):
    from rdkit import Chem
    root=Path(CONFIG['scratch'])/('record-%09d'%ordinal)
    resumed=root.exists()
    if not resumed:root.mkdir(parents=True,exist_ok=False)
    z=structure['atomic_numbers'];coords=structure['coordinates_A']
    symbols=[Chem.GetPeriodicTable().GetElementSymbol(int(value)) for value in z]
    text=str(len(z))+'\nB6 existing source geometry Angstrom; no optimization; charge=%d spin=%d\n'%(charge,spin)
    text+='\n'.join('%s %.12f %.12f %.12f'%(symbol,*xyz) for symbol,xyz in zip(symbols,coords))+'\n'
    if resumed:
        if not (root/'input.xyz').exists() or (root/'input.xyz').read_text(encoding='ascii')!=text:
            return None,None,'EXISTING_NATIVE_INPUT_DIFFERS_NO_OVERWRITE',str(root),{'scf_iterations':None,'converged':None}
    else:(root/'input.xyz').write_text(text,encoding='ascii')
    if not resumed:(root/'native.inp').write_text('$write\n json=true\n$end\n',encoding='ascii')
    env=dict(os.environ,**CONFIG.get('xtb_environment',{}))
    command=[CONFIG['xtb_executable'],'input.xyz','--input','native.inp','--gfn','2','--chrg',str(charge),'--uhf',str(spin)]
    returncode=None
    if not resumed:
        with (root/'process.out').open('wb') as stream:
            process=subprocess.run(command,cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                timeout=CONFIG.get('native_singlepoint_timeout_seconds',900))
        returncode=process.returncode
    elif not (root/'process.out').exists():
        return None,None,'EXISTING_NATIVE_OUTPUT_UNRESOLVED_NO_RETRY',str(root),{'scf_iterations':None,'converged':None}
    output=(root/'process.out').read_bytes()
    convergence=SCF.extract_scf('xtb_singlepoint',[{'name':'process.out','data':output}])
    parsed=PARSER.parse_xtb(root,symbols)
    values=PARSER.project_values('xtb_singlepoint',parsed)
    if (resumed and not parsed.get('normal_end')) or returncode not in (None,0) or convergence['converged'] is not True:
        return None,None,'CALCULATION_FAILED_OR_UNCONVERGED',str(root),convergence
    if values.get('energy_Eh') is None:
        return None,None,'PROPERTY_FAILED_ENERGY_MISSING',str(root),convergence
    for field in ('charges_e','D4_atomic_C6_au','D4_atomic_alpha_bohr3'):
        array=values.get(field)
        if array and (len(array)!=len(z) or any(not math.isfinite(v) for v in array)):
            return None,None,'PROPERTY_FAILED_ATOM_ALIGNMENT:'+field,str(root),convergence
    for row in values.get('wiberg_pairs',[]):
        if not 0<=row['i']<len(z) or not 0<=row['j']<len(z):
            return None,None,'PROPERTY_FAILED_BOND_INDEX_ALIGNMENT',str(root),convergence
    return finite_or_none(values),quantum_features(values),('SUCCESS_REUSED_CLOSED_NATIVE_OUTPUT_EXIT_UNKNOWN' if resumed else 'SUCCESS'),str(root),convergence


def one(item):
    from rdkit import Chem
    ordinal,member=item
    result={'source_ordinal':ordinal,'dataset':member['dataset'],'member_uid':member['member_uid'],
        'sample_id':str(member.get('sample_id')),'source_fold':str(member.get('fold')),
        'rdkit_values':[float('nan')]*len(DESCRIPTORS),'rdkit_mask':[False]*len(DESCRIPTORS),
        'rdkit_status':'NOT_READY','xtb_status':'NOT_READY','xtb_raw_json':None,'xtb_features_json':None,
        'xtb_scf_iterations':None,'xtb_converged':None,'native_atomic_numbers':None,
        'source_atom_ids':None,'charge':None,'unpaired_electrons':None,'native_scratch':None,'error':None}
    try:
        structure=source_structure(member);mol=structure['mol'];z=structure['atomic_numbers']
        result['geometry_reason']=structure['geometry_reason']
        result['native_atomic_numbers']=z;result['source_atom_ids']=list(range(len(z))) if z is not None else None
        if mol is not None:
            graph=Chem.RemoveHs(Chem.Mol(mol))
            for index,(_,function) in enumerate(DESCRIPTORS):
                try:
                    value=float(function(graph))
                    if math.isfinite(value):result['rdkit_values'][index]=value;result['rdkit_mask'][index]=True
                except Exception:pass
            result['rdkit_status']='COMPLETE' if all(result['rdkit_mask']) else 'PARTIAL_EXPLICIT_MISSING'
        else:result['rdkit_status']='SOURCE_GRAPH_UNDETERMINED'
        charge,spin,reason=electronic_state(mol,z,structure['coordinates_A'])
        result.update(charge=charge,unpaired_electrons=spin)
        if reason:result['xtb_status']=reason
        else:
            raw,features,status,scratch,scf=xtb(structure,charge,spin,ordinal)
            result.update(xtb_status=status,native_scratch=scratch,xtb_scf_iterations=scf['scf_iterations'],xtb_converged=scf['converged'],
                xtb_raw_json=json.dumps(raw,allow_nan=False) if raw is not None else None,
                xtb_features_json=json.dumps(features,allow_nan=False) if features is not None else None)
    except subprocess.TimeoutExpired as exc:result.update(xtb_status='TIMEOUT_ORIGINAL_NATIVE_900S',error=repr(exc),
        native_scratch=str(Path(CONFIG['scratch'])/('record-%09d'%ordinal)))
    except Exception as exc:result.update(error=repr(exc),xtb_status='SOURCE_OR_IMPLEMENTATION_FAILED')
    return result