"""Original native identities, seed and conformer-order/Kabsch objects."""
from __future__ import annotations
import hashlib,math,pathlib,sys
from workflows.data_v1_final.conformers import selection as SEL
from . import contract as C


def originals(initialize=False):
    from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as F
    refs=C.source_check();common=F.module('common',refs['common']);F.module('selection',refs['selection'])
    science=F.module('science',refs['science'])
    native=common.load_science({'science_source_pins':[refs['proper_Kabsch'],refs['native_prepare']]})
    C.need(pathlib.Path(native.__file__).absolute()==pathlib.Path(refs['proper_Kabsch']['path'])
        and pathlib.Path(sys.modules['prepare'].__file__).absolute()==pathlib.Path(refs['native_prepare']['path'])
        and pathlib.Path(SEL.__file__).absolute()==pathlib.Path(refs['selection']['path'])
        and native.rmsd.__globals__ is native.__dict__,'ORIGINAL_NATIVE_READER_AND_KABSCH_SELECTION_MODULE_OBJECTS')
    if initialize:
        native.worker_init()  # Original reader/log/thread setup; no process()/UFF call.
        from rdkit import rdBase
        C.need(common.version_tuple(rdBase.rdkitVersion)==(2025,9,5),'ORIGINAL_RDKIT2025_09_5')
    return native,science,common


def physical_key(row):
    source=row['geometry_source'];C.need(source in ('pm7','uff_sprime'),'TWO_ORDINARY_SOURCES_ONLY')
    C.need(type(row['molecule_id']) is str and row['molecule_id'] and type(row['geometry_id']) is str and row['geometry_id'],'ACTUAL_OPAQUE_SOURCE_IDS')
    if source=='pm7':
        native=row['native_record_id'];C.need(type(native) is str and native and row['sprime_conf_idx'] is None,'PM7_NATIVE_RECORD_ID_ONLY')
        return source,row['molecule_id'],native
    idx=row['sprime_conf_idx'];C.need(type(idx) is int and 0<=idx<2**63,'REAL_NONBOOL_PHYSICAL_INT64_SPRIME_INDEX')
    return source,row['molecule_id'],idx


def order_rows(mid,bases,mol,native,check=None):
    result=[]
    C.need(len({physical_key(r) for r in bases})==len(bases),'DISTINCT_NATIVE_BASES_NO_CLONED_PHYSICAL_ROW')
    for source in ('pm7','uff_sprime'):
        selected=[r for r in bases if r['geometry_source']==source];C.need(selected,'BOTH_ORIGINAL_ORDINARY_DOMAINS')
        rows=[];by_id={}
        for row in selected:
            C.need(row['parent_geometry_id'] is None and row['view_id'] is None
                and type(row['order_energy']) is float and math.isfinite(row['order_energy']),'ACTUAL_FINITE_SOURCE_ENERGY_NOT_ZERO_FILL')
            identity=physical_key(row)[2];by_id[identity]=row['geometry_id']
            rows.append({'conformer_id':identity,'energy':row['order_energy'],'coordinates':row['positions_A']})
        def distance(left,right):
            if check is not None:check()
            return native.rmsd(mol,left['coordinates'],right['coordinates'])
        value=SEL.conformer_orders(rows,distance,mid,source,C.ORDER_SEED)
        for kind,ids in value.items():
            C.need(len(ids)==len(rows) and set(ids)==set(by_id),'ORIGINAL_THREE_COMPLETE_ORDER_PERMUTATIONS')
            result += [{'molecule_id':mid,'geometry_source':source,'order_type':kind,'method':kind,'rank':rank,'geometry_id':by_id[key]}
                for rank,key in enumerate(ids)]
    return result


def child_identity(base,record_id,calc,execution,input_sha):
    # A registered view identity from the actual input identity, never geometry
    # inference from a task name, equal xyz, filename or N1 collection marker.
    import json,re
    C.need(all(type(v) is str and v for v in (record_id,calc,execution)) and type(input_sha) is str
        and re.fullmatch('[0-9a-f]{64}',input_sha) is not None,'ACTUAL_CHILD_EXECUTION_IDENTITY')
    wire=[base['geometry_source'],base['geometry_id'],record_id,calc,execution,input_sha]
    digest=hashlib.sha256(json.dumps(wire,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return 'actual-input-child:'+digest,'actual_wp5_perturbed_input_v1'
