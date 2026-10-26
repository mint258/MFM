"""Only attach canonical HOF to inherited IDs/matrix; call frozen ordering."""
from __future__ import annotations
import math
from . import contract as C
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1.core import geometry_orders
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1.contract import validate_hof


def view(packet,packet_reference,golden_reference):
    """Drop coordinate copies from worker IPC, retain exact original source refs."""
    C.need(packet['schema']=='PM7_INDEPENDENT_MOLECULE_CACHE_V1' and
      packet['status']=='PM7_GEOMETRY_CACHE_COMPLETE_HOF_PENDING','ACTUAL_GEOMETRY_ONLY_PACKET_REQUIRED')
    records=packet['source_records'];ids=packet['pair_rmsd_record_ids'];matrix=packet['pair_rmsd_A']
    C.need(len(records)==packet['pm7_count']==len(ids)==len(set(ids)) and
      set(ids)=={r['record_id'] for r in records}=={r['conformer_id'] for r in packet['pm7']},'SOURCE_AND_MATRIX_IDS_EXACT')
    C.need(len(matrix)==len(ids) and all(len(row)==len(ids) for row in matrix)
      and all(math.isfinite(x) and x>=0 for row in matrix for x in row),'EXACT_FINITE_DIRECTIONAL_MATRIX')
    return {'molecule_id':packet['molecule_id'],'geometry_packet_reference':packet_reference,
      'golden_reference':golden_reference,'source_records':records,'ids':ids,'matrix':matrix,
      'matrix_sha256':C.digest([ids,matrix]),'original_orders':packet['orders'],
      'original_unique_representatives':packet['unique_representatives'],
      'geometry_hashes':{r['conformer_id']:r['geometry_sha256'] for r in packet['pm7']},
      'original_cache_key':packet['cache_key'],'pm7_count':packet['pm7_count']}


def golden_compare(derived,old):
    if old is None:return {'status':'NOT_A_GOLDEN_MEMBER'}
    C.need(old['status']=='D7_MOLECULE_PROFILE_COMPLETE' and old['molecule_id']==derived['molecule_id'],'EXACT_OLD_GOLDEN_MOLECULE')
    ids=set(derived['hof_by_record']);C.need(ids==set(old['hof_by_record']),'GOLDEN_NATIVE_RECORD_ID_SET_CHANGED')
    if not derived['hof_range_complete']:
        return {'status':'PENDING_CURRENT_CANONICAL_HOF','not_reported_as_energy_mismatch':True}
    if not old.get('hof_range_complete'):
        return {'status':'PENDING_OLD_GOLDEN_CANONICAL_HOF','not_reported_as_energy_mismatch':True}
    equal_bits=all(C.bits(derived['hof_by_record'][rid]['value_kcal_mol'])==
                   C.bits(old['hof_by_record'][rid]['value_kcal_mol']) for rid in ids)
    equal_state=all({k:v for k,v in derived['hof_by_record'][rid].items() if k!='value_kcal_mol'}==
                    {k:v for k,v in old['hof_by_record'][rid].items() if k!='value_kcal_mol'} for rid in ids)
    equal_orders=(derived['orders']['energy']==old['orders']['pm7']['energy'] and
                  derived['orders']['diversity']==old['orders']['pm7']['diversity'])
    equal_geometry=(derived['geometry_hashes']==old['geometry_hashes']['pm7'] and
      derived['orders']['fixed_random']==old['orders']['pm7']['fixed_random'] and
      derived['inherited_unique_representatives']==old['unique_representatives']['pm7'])
    return {'status':'GOLDEN_CANONICAL_HOF_BITS_STATE_AND_ORDERS_EQUAL' if
      equal_bits and equal_state and equal_orders and equal_geometry else 'GOLDEN_MISMATCH_HOLD',
      'hof_float64_bits_equal':equal_bits,'hof_field_state_equal':equal_state,
      'energy_and_diversity_orders_equal':equal_orders,'inherited_geometry_random_unique_equal':equal_geometry,
      'numeric_tolerance_added':False}


def augment(task,hof,owner_provenance,old=None):
    mid=task['molecule_id'];ids=task['ids'];matrix=task['matrix']
    C.need(set(hof)==set(ids),'ENTIRE_EXISTING_MOLECULE_HOF_MAP')
    C.need(C.digest([ids,matrix])==task['matrix_sha256'],'INHERITED_DIRECTIONAL_MATRIX_CHANGED')
    for value in hof.values():validate_hof(value)
    # Stored directional distances, including their actual diagonals. No RMSD call.
    index={rid:i for i,rid in enumerate(ids)}
    distance=lambda left,right:matrix[index[left['conformer_id']]][index[right['conformer_id']]]
    rows=[{'conformer_id':rid,'energy':hof[rid]['value_kcal_mol'] if hof[rid]['valid'] else None} for rid in ids]
    orders=geometry_orders(rows,distance,mid,'pm7')
    C.need(orders['fixed_random']==task['original_orders']['fixed_random'],'ORIGINAL_FIXED_RANDOM_ORDER_CHANGED')
    energies=[r['energy'] for r in rows if r['energy'] is not None]
    result={'schema':'PM7_CANONICAL_HOF_ORDER_AUGMENTATION_V1','molecule_id':mid,
      'status':'CANONICAL_HOF_AND_DERIVED_ORDERS_COMPLETE' if len(energies)==len(ids) else 'CANONICAL_HOF_PENDING_GEOMETRY_RETAINED',
      'geometry_packet_reference':task['geometry_packet_reference'],'original_cache_key':task['original_cache_key'],
      'geometry_hashes':task['geometry_hashes'],'inherited_directional_matrix_sha256':task['matrix_sha256'],
      'inherited_pair_rmsd_record_ids':ids,'inherited_unique_representatives':task['original_unique_representatives'],
      'records':len(ids),'hof_by_record':hof,'hof_valid_count':len(energies),'hof_range_complete':len(energies)==len(ids),
      'hof_range_kcal_mol':max(energies)-min(energies) if energies else None,
      'hof_float64_bit_signatures':{rid:C.bits(v['value_kcal_mol']) if v['valid'] else None for rid,v in hof.items()},
      'hof_source_provenance_by_record':owner_provenance,'orders':orders,
      'convergence_null_review_records':sum(bool(v['convergence_null_review']) for v in hof.values()),
      'native_energy_fallback_used':False,'new_LMDB_reads':0,'new_geometry_or_RMSD_calls':0,
      'new_UFF_calls':0,'new_QM_calls':0,'common':False,'full_cache_release':False,
      'physical_int64_or_order_manifest_release':False}
    result['golden_comparison']=golden_compare(result,old);result['golden_reference']=task['golden_reference']
    return result
