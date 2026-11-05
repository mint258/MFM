"""Assemble one closed v3.0 MID into raw compact v3.1 arrays.

No IO beyond the supplied readonly OldStore handles, no hashes/F64/normalization.
Canonical atom permutations map source index -> M index; coordinates/vectors are
not rotated. Duplicate target sources must have identical original value/mask
arrays after that reversible reindexing; validity is never unioned.
"""
from __future__ import annotations
from collections import Counter
import json
import numpy as np


class ScientificLayoutError(ValueError):
    """The fixed compact layout cannot retain the observed scientific content."""


def _need(value,message):
    if not value:raise ScientificLayoutError(message)


def _integer(array,shape,name,maximum=None):
    a=np.asarray(array)
    _need(a.shape==shape and a.dtype.kind in 'iu',name+': original integer shape required')
    _need(not a.size or np.all(a>=0),name+': negative index')
    if maximum is not None:_need(not a.size or np.all(a<=maximum),name+': integer overflow')
    return a.astype(np.int64,copy=False)


def _bonds(arrays,n):
    raw=np.asarray(arrays['native_bond_index']);orders=np.asarray(arrays['native_bond_order'])
    _need(raw.ndim==2 and raw.shape[0]==2,'native_bond_index must retain original [2,E] layout')
    pairs=_integer(raw.T,(raw.shape[1],2),'bonds',n-1)
    codes=_integer(orders,(len(pairs),),'bond order',255)
    return pairs,codes


def _edge_set(pairs,codes):
    result={}
    for (i,j),code in zip(pairs,codes):
        key=(min(int(i),int(j)),max(int(i),int(j)))
        _need(key not in result or result[key]==int(code),'inconsistent duplicate native bond order')
        result[key]=int(code)
    return result


def _permutation(reference_z,reference_pairs,reference_codes,z,pairs,codes):
    n=len(reference_z)
    _need(len(z)==n,'different atom counts cannot share one M.Z')
    if np.array_equal(z,reference_z) and _edge_set(pairs,codes)==_edge_set(reference_pairs,reference_codes):return np.arange(n,dtype=np.int64),'SOURCE_Z_SEQUENCE_AND_BOND_GRAPH'
    _need(Counter(map(int,z))==Counter(map(int,reference_z)),'atomic number multisets differ; no reversible permutation')
    from rdkit import Chem
    def molecule(numbers,edges):
        rw=Chem.RWMol()
        for number in numbers:rw.AddAtom(Chem.Atom(int(number)))
        bond_types={1:Chem.BondType.SINGLE,2:Chem.BondType.DOUBLE,3:Chem.BondType.TRIPLE,4:Chem.BondType.AROMATIC}
        for (i,j),code in sorted(edges.items()):
            _need(code in bond_types and i!=j,'unsupported original bond topology for atom permutation')
            rw.AddBond(i,j,bond_types[code])
            if code==4:
                rw.GetAtomWithIdx(i).SetIsAromatic(True);rw.GetAtomWithIdx(j).SetIsAromatic(True)
        mol=rw.GetMol();mol.UpdatePropertyCache(strict=False);Chem.GetSymmSSSR(mol);return mol
    try:
        reference=molecule(reference_z,_edge_set(reference_pairs,reference_codes))
        source=molecule(z,_edge_set(pairs,codes))
        # Query atom k is source k; returned reference atom is its M index.
        match=reference.GetSubstructMatch(source,useChirality=False)
    except ScientificLayoutError:raise
    except (ValueError,RuntimeError)as error:raise ScientificLayoutError('original bond graph cannot supply a reversible atom permutation')from error
    _need(len(match)==n and len(set(match))==n,'source atom sequence differs and no reversible graph isomorphism exists')
    perm=np.asarray(match,dtype=np.int64)
    _need(np.array_equal(reference_z[perm],z)and _edge_set(perm[pairs],codes)==_edge_set(reference_pairs,reference_codes),'graph permutation is not reversible')
    return perm,'RDKIT_BOND_GRAPH_ISOMORPHISM'


def _same(a,b):
    a,b=np.asarray(a),np.asarray(b)
    return a.shape==b.shape and a.dtype==b.dtype and a.tobytes()==b.tobytes()


def _qa(entry,geometry_role=None):
    return dict(path=entry['path'],gid=entry['gid'],kind=entry['kind'],geometry_role=geometry_role)


def _append_unique(rows,value):
    if value not in rows:rows.append(value)


def _append_target_qa(rows,entry,tid):
    for row in rows:
        if row['path']==entry['path']and row['gid']==entry['gid']and row['kind']=='labels':
            if tid not in row['target_ids']:row['target_ids'].append(tid)
            return
    rows.append(dict(_qa(entry),target_ids=[tid]))


def _key(metadata,descriptor):
    source=metadata.get('geometry_source',descriptor.get('geometry_source'))
    _need(source in('pm7','uff_sprime'),'only original PM7/UFF geometry domains are supported')
    if source=='pm7':
        physical=metadata.get('native_record_id');_need(isinstance(physical,str)and physical,'PM7 requires its original native_record_id')
    else:
        physical=metadata.get('sprime_conf_idx');_need(type(physical)is int and physical>=0,'UFF requires its original sprime_conf_idx')
        alias=metadata.get('storage_physical_alias')
        if alias is not None:
            _need(metadata.get('ordinary_sprime')is False and isinstance(alias,str)and alias,'only explicit nonordinary storage aliases may separate scientific-ID collisions')
            physical=alias
    return source,physical


def _is_base(metadata):return metadata.get('parent_geometry_id')is None and metadata.get('view_id')is None


def _provenance(metadata):
    value=metadata.get('actual_geometry_provenance',{})
    if not isinstance(value,dict):return {}
    value=value.get('source_provenance_json',value)
    if isinstance(value,str):
        try:value=json.loads(value)
        except json.JSONDecodeError:raise ScientificLayoutError('invalid existing source_provenance_json')
    return value if isinstance(value,dict)else {}


def _task(metadata):
    source=_provenance(metadata);binding=source.get('actual_original_binding',{})
    original=metadata.get('actual_geometry_provenance',{})
    candidates=[metadata.get('calc_type'),metadata.get('task_name'),original.get('calc_type'),original.get('task'),source.get('calc_type'),source.get('task'),binding.get('calc_type'),binding.get('task')]
    observed={v for v in candidates if isinstance(v,str)and v}
    _need(len(observed)<=1,'existing geometry task witnesses disagree')
    return next(iter(observed),None)


def _geometry_task(entry,items,layouts):
    task=_task(entry['metadata'])
    if task is not None:return task
    tasks=set()
    for label in items:
        if label['kind']!='labels'or label['gid']!=entry['gid']:continue
        for locator in label['metadata'].get('permanent_source_locators',{}).values():
            if isinstance(locator.get('task'),str):tasks.add(locator['task'])
        for tid,layout in layouts.items():
            if 'values/'+tid not in label['arrays']and 'transport/'+tid+'/values'not in label['arrays']:continue
            witness=layout.get('mapping_target',{}).get('native_target_identity',{})
            if isinstance(witness.get('task'),str):tasks.add(witness['task'])
    _need(len(tasks)<=1,'same actual input geometry has conflicting existing task witnesses')
    return next(iter(tasks),None)


def _source_identity(entry):
    m=entry['metadata'];keys=('native_record_id','sprime_conf_idx','parent_geometry_id','view_id','available_base_order_ranks',
       'actual_input_bundle_sha256','actual_input_file_sha256','geometry_sha256','atom_order_sha256','ordered_entry_domains',
       'actual_geometry_manifest_reference','actual_field_geometry_claims_reference')
    result=dict(path=entry['path'],gid=entry['gid'],**{key:m[key]for key in keys if key in m})
    locator_keys=('source_reference','physical_row','row_group','row_within_group','record_id','molecule_id','task','record_ordinal','source_index','row_number','source_file_id')
    result['source_rows']={tid:{key:value[key]for key in locator_keys if key in value}for tid,value in m.get('permanent_source_locators',{}).items()}
    return result


def _masked(values,valid):
    values=np.asarray(values);valid=np.asarray(valid)
    _need(values.dtype==np.dtype('<f4')and valid.shape==values.shape,'original F32 value/valid shape required')
    _need(valid.dtype.kind in 'iu'and np.all((valid==0)|(valid==1)),'original binary valid mask required')
    result=values.copy();result[valid==0]=np.nan;return result


def _strings(arrays,prefix,name):
    raw=np.asarray(arrays[prefix+name+'_utf8']);offset=np.asarray(arrays[prefix+name+'_offsets'])
    _need(raw.dtype==np.dtype('u1')and offset.ndim==1 and offset.dtype.kind in 'iu'and len(offset)>0
      and offset[0]==0 and offset[-1]==len(raw)and np.all(offset[1:]>=offset[:-1]),'original r73 UTF8 offset layout required')
    body=raw.tobytes()
    return [body[int(a):int(b)].decode('utf-8')for a,b in zip(offset[:-1],offset[1:])]


def _r73(entry,tid,perm):
    arrays=entry['arrays'];p='transport/'+tid+'/'
    values=np.asarray(arrays[p+'values']);k=len(values)
    atoms_i=_integer(arrays[p+'atom_i'],(k,),'r73 atom_i',len(perm)-1);atoms_j=_integer(arrays[p+'atom_j'],(k,),'r73 atom_j',len(perm)-1)
    ordinal=_integer(arrays[p+'ordinal'],(k,),'r73 ordinal')
    _need(np.array_equal(ordinal,np.arange(k,dtype=np.int64)),'r73 source K order must be retained')
    basis_i,basis_j,channel=(_strings(arrays,p,name)for name in('basis_i','basis_j','channel'))
    present=_integer(arrays[p+'channel_present'],(k,),'r73 channel presence',1)
    onsite_present=_integer(arrays[p+'onsite_present'],(k,),'r73 onsite presence',1)
    onsite=_integer(arrays[p+'onsite'],(k,),'r73 onsite',1)
    _need(len(basis_i)==len(basis_j)==len(channel)==k,'r73 channel rows differ from K')
    channels=[(a,b,c if flag else None)for a,b,c,flag in zip(basis_i,basis_j,channel,present)]
    pairs=np.column_stack((perm[atoms_i],perm[atoms_j]));valid=np.asarray(arrays['valid/'+p])
    masked=_masked(values,valid)
    return dict(pairs=pairs,channels=channels,onsite=np.where(onsite_present,1+onsite,0).astype('u1'),
      raw=values.copy(),valid=valid.copy(),masked=masked)


def assemble_molecule(mid,readers,schema,*,include_uff_labels=False):
    """Return M arrays, physical P/U records, ID aliases and existing QA refs."""
    layouts=schema['target_layout'];columns=schema['columns'];entries=[]
    for descriptor,store in readers:
        descriptor=dict(descriptor);path=str(descriptor.get('path',store.path));kind=descriptor.get('kind',store.schema['kind'])
        for gid in store.records_for_molecule(mid):
            metadata,arrays=store.get(gid)
            _need(metadata.get('molecule_id')==mid,'legacy molecule index points to another MID')
            _need(kind in('geometry','labels')and store.schema['kind']==kind,'descriptor/store kind mismatch')
            key=_key(metadata,descriptor)
            if kind=='labels'and key[0]=='uff_sprime'and not include_uff_labels:raise ScientificLayoutError('unexpected UFF D/P labels in this explicitly geometry-only U trial')
            entries.append(dict(path=path,gid=gid,kind=kind,descriptor=descriptor,metadata=metadata,arrays=arrays,key=key))
    geometries=[e for e in entries if e['kind']=='geometry']
    _need(geometries,'MID has no original geometry record')
    bases=[e for e in geometries if _is_base(e['metadata'])]
    _need(bases,'MID has no actual ordinary base geometry; a program-input view cannot replace it')
    reference=min(bases,key=lambda e:(e['key'][0]!='pm7',bool(e['descriptor'].get('is_holdout')),str(e['key'][1]),e['gid'],e['path']))
    z=np.asarray(reference['arrays']['atomic_numbers']);_need(z.ndim==1 and z.dtype.kind in'iu'and np.all((z>0)&(z<=255)),'M.Z requires original atomic numbers')
    n=len(z);_need(0<n<=32768,'atom indices cannot fit signed int16 or no atoms exist')
    bonds,bond_orders=_bonds(reference['arrays'],n);permutations={};differences=[];by_gid={}
    for e in geometries:
        a=e['arrays'];other_z=np.asarray(a['atomic_numbers']);p,c=_bonds(a,len(other_z))
        perm,evidence=_permutation(z,bonds,bond_orders,other_z,p,c)
        e.update(perm=perm,permutation_evidence=evidence)
        mapped=perm[p]
        if _edge_set(mapped,c)!=_edge_set(bonds,bond_orders):
            differences.append(dict(mid=mid,path=e['path'],gid=e['gid'],native_record_id=e['metadata'].get('native_record_id'),
              sprime_conf_idx=e['metadata'].get('sprime_conf_idx'),source_to_M=perm.tolist(),native_bond_index=p.T.tolist(),
              native_bond_order=c.tolist(),canonical_M_bond_index=bonds.T.tolist(),canonical_M_bond_order=bond_orders.tolist()))
        by_gid.setdefault(e['gid'],[]).append(e)
    for e in entries:
        if e['kind']=='labels':
            options=by_gid.get(e['gid'],[])
            _need(options,'label geometry has no actual geometry-store record')
            _need(all(np.array_equal(v['perm'],options[0]['perm'])for v in options),'same geometry ID has conflicting atom permutations')
            e['perm']=options[0]['perm'];e['permutation_evidence']=options[0]['permutation_evidence']
    groups={}
    for e in entries:groups.setdefault(e['key'],[]).append(e)
    roles={e['metadata'].get('effective_role')for e in entries if not e['descriptor'].get('is_holdout')}
    roles.discard(None);_need(len(roles)==1,'one original effective molecule role required')
    role=next(iter(roles));book=schema['role_codebook'];matches=[v for k,v in book.items()if k.upper()==str(role).upper()]
    _need(len(matches)==1 and type(matches[0])is int and 0<=matches[0]<=255,'explicit schema role codebook required')
    m_arrays={1:np.asarray(z,dtype='u1'),2:np.asarray(bonds,dtype='<i2'),3:np.asarray(bond_orders,dtype='u1'),
      4:np.full(len(columns['d20']),np.nan,dtype='<f4'),5:np.asarray(matches[0],dtype='u1')}
    m_qa=[_qa(reference,'base')];d20_seen={};p_records=[];u_records=[]
    def storage_order(item):
        source,physical=item[0];meta=item[1][0]['metadata']
        return (0,0,0,str(physical)) if source=='pm7' else (1,int(not meta.get('ordinary_sprime',True)),int(meta['sprime_conf_idx']),str(physical))
    for key,items in sorted(groups.items(),key=storage_order):
        source,physical=key;geo=[e for e in items if e['kind']=='geometry'];base=[e for e in geo if _is_base(e['metadata'])]
        _need(base,'physical conformer has no actual base coordinates')
        base.sort(key=lambda e:(bool(e['descriptor'].get('is_holdout')),e['gid'],e['path']));chosen=base[0]
        def positions(e):
            a=np.asarray(e['arrays']['positions_A']);_need(a.dtype==np.dtype('<f4')and a.shape==(n,3),'original F32 geometry shape required')
            return a[np.argsort(e['perm'])].copy()
        pos=positions(chosen)
        for e in base[1:]:_need(_same(positions(e),pos),'two actual base sources disagree on original F32 positions')
        ranks={}
        for e in base:
            for kind,value in e['metadata'].get('available_base_order_ranks',{}).items():
                _need(type(value)is int and value>=0 and (kind not in ranks or ranks[kind]==value),'conflicting existing conformer rank')
                ranks[kind]=value
        holdout=any(bool(e['descriptor'].get('is_holdout'))for e in base)
        identity=dict(storage_physical_alias=chosen['metadata'].get('storage_physical_alias'),diagnostic_only=chosen['metadata'].get('diagnostic_only',False),excluded_from_all_training=chosen['metadata'].get('excluded_from_all_training',False),ordinary_sprime=chosen['metadata'].get('ordinary_sprime',True),geometry_source=source,native_record_id=chosen['metadata'].get('native_record_id'),sprime_conf_idx=chosen['metadata'].get('sprime_conf_idx'),
          legacy_geometry_ids=sorted({e['gid']for e in items}),base_geometry_id=chosen['gid'],is_holdout=holdout,available_base_order_ranks=ranks,
          atom_permutation_new_to_old=np.argsort(chosen['perm']).tolist(),atom_permutations=[dict(path=e['path'],gid=e['gid'],source_to_M=e['perm'].tolist())for e in items],
          source_records=[_source_identity(e)for e in items])
        qa=[_qa(chosen,'base')];record=dict(arrays={21:pos},r73_channels=[],identity=identity,qa_sources=qa)
        if source=='uff_sprime'and not include_uff_labels:u_records.append(record);continue
        record['arrays'][22]=np.full((n,3),np.nan,dtype='<f4')
        perturbed=[e for e in geo if e['metadata'].get('view_id')=='actual_wp5_perturbed_input_v1'
          and _geometry_task(e,items,layouts)=='xtb_perturbed_gradient']
        if perturbed:
            first=perturbed[0];pert_pos=positions(first)
            for e in perturbed[1:]:_need(_same(positions(e),pert_pos),'multiple real perturbed Source geometries conflict')
            record['arrays'][22]=pert_pos;_append_unique(qa,_qa(first,'perturbed'));identity['perturbed_geometry_ids']=sorted({e['gid']for e in perturbed})
        # Same physical native RID folds the actual program-input views. Their
        # existing field-specific labels retain independent compact columns.
        arrays=record['arrays'];arrays[23]=np.full(len(columns['mol_labels']),np.nan,dtype='<f4')
        arrays[24]=np.full((n,len(columns['atom_labels'])),np.nan,dtype='<f4')
        arrays[25]=np.full((n,len(columns['atom_vectors']),3),np.nan,dtype='<f4')
        target_seen={};pair_values=[];ordered=None;ordered_tid=None
        for e in items:
            if e['kind']!='labels':continue
            old=e['arrays'];perm=e['perm'];inverse=np.argsort(perm);contributed_tids=[]
            actual_tids={name[len('values/'):]for name in old if name.startswith('values/')}
            actual_tids.update(name.split('/')[1]for name in old if name.startswith('transport/')and name.endswith('/values'))
            for tid in sorted(actual_tids):
                _need(tid in layouts,'old enabled target missing from compact schema')
                layout=layouts[tid];name=layout['array_name'];indices=layout['column_indices']
                if name=='r73_ordered':
                    value=_r73(e,tid,perm)
                    _need(ordered_tid in(None,tid),'multiple distinct r73 targets cannot share one four-array ordered layout')
                    if ordered is not None:
                        _need(value['channels']==ordered['channels']and all(_same(value[k],ordered[k])for k in('pairs','onsite','raw','valid')),'duplicate r73 Source values/masks/K identities differ')
                    else:ordered=value;ordered_tid=tid;contributed_tids.append(tid)
                    continue
                _need('values/'+tid in old and 'valid/'+tid in old,'original value and mask must coexist')
                raw=np.asarray(old['values/'+tid]);valid=np.asarray(old['valid/'+tid]);_masked(raw,valid)
                if name in('atom_labels','atom_vectors'):
                    _need(raw.shape[0]==n,'atom target does not follow geometry atom count');raw=raw[inverse];valid=valid[inverse]
                pairs=None
                if name=='pair_labels':
                    _need('pairs/'+tid in old,'original sparse pair index required')
                    pair=np.asarray(old['pairs/'+tid]);_need(pair.ndim==2 and pair.shape[1]==2,'original pair shape required')
                    pairs=perm[_integer(pair,pair.shape,'pair endpoints',n-1)]
                state=(raw.copy(),valid.copy(),None if pairs is None else pairs.copy())
                seen=d20_seen if name=='d20'else target_seen
                if tid in seen:
                    prior=seen[tid];_need(_same(prior[0],state[0])and _same(prior[1],state[1])and ((prior[2]is None and state[2]is None)or(prior[2]is not None and state[2]is not None and _same(prior[2],state[2]))),'duplicate target original values/valid/index differ: '+tid)
                    continue
                seen[tid]=state;value=_masked(raw,valid)
                if name!='d20':contributed_tids.append(tid)
                if name=='d20':
                    _need(value.size==len(indices)==1,'D20 target must be one molecule scalar');m_arrays[4][indices]=value.reshape(-1);_append_target_qa(m_qa,e,tid)
                elif name=='mol_labels':
                    _need(value.size==len(indices),'molecule target component count differs');arrays[23][indices]=value.reshape(-1)
                elif name=='atom_labels':
                    _need(value.shape==(n,)and len(indices)==1,'atom scalar layout differs');arrays[24][:,indices[0]]=value
                elif name=='atom_vectors':
                    _need(value.shape==(n,3)and len(indices)==1,'atom vector layout differs');arrays[25][:,indices[0],:]=value
                elif name=='pair_labels':
                    _need(value.shape==(len(pairs),)and len(indices)==1,'sparse scalar pair layout differs');pair_values.append((pairs,value,indices[0]))
                else:raise ScientificLayoutError('unsupported declared target layout: '+str(name))
            for tid in contributed_tids:_append_target_qa(qa,e,tid)
        all_pairs={tuple(map(int,row))for pairs,_,_ in pair_values for row in pairs}
        if ordered is not None:all_pairs.update(tuple(map(int,row))for row in ordered['pairs'])
        union=sorted(all_pairs);lookup={pair:i for i,pair in enumerate(union)}
        arrays[26]=np.asarray(union,dtype='<i2').reshape(-1,2);arrays[27]=np.full((len(union),len(columns['pair_labels'])),np.nan,dtype='<f4')
        assigned=set()
        for pairs,values,column in pair_values:
            for pair,value in zip(pairs,values):
                row=lookup[tuple(map(int,pair))];cell=(row,column)
                _need(cell not in assigned,'ordinary pair target repeats a pair; fixed scalar cell would lose multiplicity')
                assigned.add(cell);arrays[27][row,column]=value
        if ordered is not None:
            arrays[31]=np.asarray([lookup[tuple(map(int,row))]for row in ordered['pairs']],dtype='<u4')
            arrays[33]=ordered['onsite'];arrays[34]=ordered['masked'];record['r73_channels']=ordered['channels']
        else:
            arrays[31]=np.empty(0,dtype='<u4');arrays[33]=np.empty(0,dtype='u1');arrays[34]=np.empty(0,dtype='<f4')
        (p_records if source=='pm7'else u_records).append(record)
    _need(len(p_records)<=65535 and len(u_records)<=65535,'conformer count exceeds uint16')
    m_arrays[6]=np.asarray([len(p_records),len(u_records)],dtype='<u2')
    if include_uff_labels:m_arrays[17]=np.asarray([int(r['identity']['ordinary_sprime']) for r in u_records],dtype='u1')
    for records,random_id,energy_id,diversity_id,held_id in((p_records,7,9,10,13),(u_records,8,11,12,14)):
        ordinary=[(i,record) for i,record in enumerate(records) if record['identity'].get('ordinary_sprime',True) or record['identity']['geometry_source']=='pm7']
        total=len(ordinary)
        for i,record in enumerate(records):record['identity']['conformer_index']=i
        for order,array_id in(('fixed_random',random_id),('energy',energy_id),('diversity',diversity_id)):
            found=[]
            for i,record in ordinary:
                rank=record['identity']['available_base_order_ranks'].get(order)
                if rank is None and order=='fixed_random'and record['identity']['is_holdout']:
                    rank=total-1;record['identity']['available_base_order_ranks'][order]=rank
                    record['identity']['fixed_random_rank_source']='ORIGINAL_D5_LAST_BASE_N_MINUS_ONE'
                if rank is not None:found.append((rank,i))
            if not found and order!='fixed_random':continue
            _need(len(found)==total and sorted(rank for rank,_ in found)==list(range(total)),'existing '+order+' ranks are not a complete unchanged permutation')
            m_arrays[array_id]=np.asarray([i for _,i in sorted(found)],dtype='<u2')
        m_arrays[held_id]=np.asarray([int(record['identity']['is_holdout'])for record in records],dtype='u1')
    return dict(mid=mid,role=role,m_arrays=m_arrays,p_records=p_records,u_records=u_records,
      topology_differences=differences,qa_sources=m_qa)
