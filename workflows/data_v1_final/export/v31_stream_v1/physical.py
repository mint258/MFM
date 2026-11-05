"""Original physical geometry readers and original corrected-base D3 callable."""
import collections,gzip,importlib.util,json,pickle,sys
from pathlib import Path
import numpy as np
PROJECT=Path('/share/home/zixiao/descriptor_analysis')
HANDLES=collections.OrderedDict();PACKETS=collections.OrderedDict();WIRE=None


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def native(pointer):
    """Read the original payload for graph/SMILES, with no new hash or QA pass."""
    import lmdb
    path=Path(pointer['source_path']);path=path if path.is_absolute() else PROJECT/path
    if str(path) not in HANDLES:
        if len(HANDLES)>=4:HANDLES.popitem(last=False)[1].close()
        HANDLES[str(path)]=lmdb.open(str(path),subdir=False,readonly=True,lock=False,create=False,readahead=False,max_readers=1024)
    with HANDLES[str(path)].begin() as tx:raw=tx.get(('%09d'%int(pointer['real_index'])).encode())
    if raw is None:raise ValueError('ORIGINAL_NATIVE_PHYSICAL_KEY_MISSING')
    return pickle.loads(raw)


def field(raw,key):return raw.get(key) if isinstance(raw,dict) else getattr(raw,key,None)
def array(value):return value.detach().cpu().numpy() if hasattr(value,'detach') else np.asarray(value)


def physical(pointer):
    if pointer['source_format']=='parquet':
        import pyarrow.parquet as pq
        table=pq.ParquetFile(pointer['source_path'],pre_buffer=False);index=int(pointer['source_row_index']);offset=0
        try:
            for rg in range(table.num_row_groups):
                n=table.metadata.row_group(rg).num_rows
                if index<offset+n:
                    local=index-offset;lo=0
                    for batch in table.iter_batches(row_groups=[rg],batch_size=128,use_threads=False):
                        if lo<=local<lo+batch.num_rows:result=batch.slice(local-lo,1).to_pylist()[0];break
                        lo+=batch.num_rows
                    break
                offset+=n
            else:raise ValueError('PHYSICAL_GEOMETRY_ROW_MISSING')
        finally:table.close()
    elif pointer['source_format']=='reproduction_json_gz':
        path=pointer['source_path']
        if path not in PACKETS:
            if len(PACKETS)>=8:PACKETS.popitem(last=False)
            with gzip.open(path,'rt',encoding='utf-8') as f:PACKETS[path]=json.load(f)
        packet=PACKETS[path]
        if packet['summary']['molecule_id']!=pointer['molecule_id']:raise ValueError('PHYSICAL_PACKET_MID_DIFFERS')
        result=packet['conformers'][int(pointer['source_row_index'])]
    else:raise ValueError('UNKNOWN_PHYSICAL_FORMAT:'+str(pointer['source_format']))
    accepted=pointer.get('accepted_component_kind') in ('CURRENT_CANONICAL_N1_PHYSICAL_ACCEPTED','frozen_d5_actual_heldout_geometry','closed_pprime_source_geometry') and pointer['source_format']=='parquet'
    if accepted:
        # This immutable accepted component omits the two status columns. Its
        # explicit accepted type is authority only for those absent columns;
        # an actual false/NULL status in any present column is never promoted.
        if ('status' in result and result['status']!='SUCCESS') or ('converged' in result and result['converged'] is not True):raise ValueError('ACCEPTED_N1_COMPONENT_EXPLICIT_STATUS_CONFLICT')
    elif result.get('status')!='SUCCESS' or result.get('converged') is not True:raise ValueError('PHYSICAL_GEOMETRY_NOT_CONVERGED')
    if result.get('molecule_id',pointer['molecule_id'])!=pointer['molecule_id']:raise ValueError('PHYSICAL_GEOMETRY_MID_DIFFERS')
    if pointer.get('atom_order_sha256') and (not accepted or 'atom_order_sha256' in result) and result.get('atom_order_sha256')!=pointer['atom_order_sha256']:raise ValueError('ORIGINAL_ATOM_ORDER_WITNESS_DIFFERS')
    xyz=result.get('coordinates',result.get('positions_A'))
    if xyz is None:raise ValueError('PHYSICAL_COORDINATES_MISSING')
    return result,np.asarray(xyz,dtype='<f8')


def original_wire():
    global WIRE
    if WIRE is None:
        WIRE=module('_window2_original_D3_wire',PROJECT/'runs/phase1_screening_20261011/scripts/c_engineering_wire.py')
        # Bind the same original constants directly; metadata() would compute
        # a redundant content hash. Scientific corrected_base is unmodified.
        from phychem_mfm.data.descriptor_schema import GRAPH_DESCRIPTOR_NAMES
        from phychem_mfm.model.phase1_specs import PHASE1_GRAPH_DESCRIPTOR_NAMES
        WIRE.GRAPH_NAMES=tuple(GRAPH_DESCRIPTOR_NAMES);WIRE.D23=tuple(PHASE1_GRAPH_DESCRIPTOR_NAMES)
        WIRE.D20=tuple(n for n in WIRE.D23 if n not in {'Kappa1','Kappa2','Kappa3'})
    return WIRE


def uff_d3(raw,xyz):
    """Exactly one original corrected_base call on this actual UFF geometry."""
    import torch
    wire=original_wire();source=dict(raw) if isinstance(raw,dict) else raw.clone()
    if isinstance(source,dict):source['pos']=torch.tensor(xyz,dtype=torch.float64)
    else:source.pos=torch.tensor(xyz,dtype=torch.float64)
    result,issues=wire.corrected_base(source,{'smiles':str(field(raw,'smiles') or '')})
    d3=field(result,'D_native_3D');d3=dict(d3);d3['PBF_A']=d3.pop('PBF')
    if d3.get('SASA_atom_A2') is not None:d3['SASA_atom_A2']=array(d3['SASA_atom_A2']).tolist()
    return d3,issues