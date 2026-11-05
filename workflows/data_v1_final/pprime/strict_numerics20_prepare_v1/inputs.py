"""Actual source readers and frozen exact renderer; never invoke a native program."""
import copy,hashlib,importlib.util,json,os,pathlib,stat,sys,threading
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from workflows.data_v1_final.pprime.strict_numerics15_qa_v1.prepare import targets
from workflows.data_v1_final.pprime import geometry
from workflows.data_v1_final.conformers import selection
from workflows.expansion.common_molecular_fp_main_v1.io import Body,BorrowedFile,stamp
from . import contract as C
Q=C.Q

class NoInvoke:
    """Tracing guard, not a replacement of initialize, reader, render or invoke."""
    def __init__(self,protocol):self.path=pathlib.Path(protocol['frozen_dependencies']['native_lifecycle']['path']).absolute();self.attempts=0
    def guard(self,frame,event,arg):
        if event=='call' and frame.f_code.co_name=='invoke' and pathlib.Path(frame.f_code.co_filename).absolute()==self.path:
            self.attempts+=1;raise RuntimeError('ZERO_INVOKE_PREPARATION_FORBIDS_NATIVE_INVOKE')
    def __enter__(self):
        Q.need(sys.getprofile() is None and threading.getprofile() is None,'NO_EXISTING_PROFILE_GUARD_TO_OVERWRITE')
        sys.setprofile(self.guard);threading.setprofile(self.guard);return self
    def __exit__(self,*error):sys.setprofile(None);threading.setprofile(None)

def pairs(reference,budget):
    body=Body(reference,budget)
    try:
        rows=[]
        while raw:=body.stream.readline((2<<20)+1):
            Q.need(len(raw)<=2<<20 and raw.endswith(b'\n'),'BOUNDED_COMPLETE_ORIGINAL_PAIR_LINE')
            row=json.loads(raw);Q.need(row['geometry_source']=='uff_sprime','REAL_UFF_PAIR_SOURCE');rows.append(row)
        body.check();return rows,{'reference':reference,'whole_SHA_verified_in_this_CPU_allocation':True,'stable_FD_frame':list(body.frame)}
    finally:body.close()

def selected_conformers(references,chosen,all_pairs,budget):
    """Inherit old closed whole SHA; verify current FD and selected complete rows."""
    import pyarrow as pa,pyarrow.compute as pc,pyarrow.parquet as pq
    mids={p['molecule_id'] for p in chosen};by={m:[] for m in mids};frames=[]
    for reference in references:
        path=pathlib.Path(reference['path']);Q.need(not any(p.is_symlink() for p in (path,*path.parents)),'OLD_SPRIME_NON_SYMLINK')
        first=path.lstat();Q.need(stat.S_ISREG(first.st_mode) and first.st_uid==1278 and first.st_size==reference['bytes'],'OLD_SPRIME_CURRENT_SIZE_UID')
        with path.open('rb') as stream:
            frame=stamp(os.fstat(stream.fileno()));Q.need(frame==stamp(first),'OLD_SPRIME_OPENED_FD_FRAME')
            parquet=pq.ParquetFile(BorrowedFile(stream));required={'molecule_id','sprime_conf_idx','coordinates','source_record_id','atom_order_sha256','status','converged','uff_energy_kcal_mol'}
            Q.need(required<=set(parquet.schema_arrow.names),'ORIGINAL_SPRIME_PHYSICAL_COLUMNS')
            for rg in range(parquet.num_row_groups):
                budget.check(True);index=parquet.read_row_group(rg,columns=['molecule_id','status','converged'])
                mask=pc.and_(pc.is_in(index['molecule_id'],value_set=pa.array(sorted(mids))),pc.and_(pc.equal(index['status'],'SUCCESS'),pc.equal(index['converged'],True)))
                positions=pc.indices_nonzero(mask)
                if not len(positions):continue
                for batch in parquet.iter_batches(batch_size=4096,row_groups=[rg]):
                    budget.check(True);table=pa.Table.from_batches([batch])
                    keep=pc.and_(pc.is_in(table['molecule_id'],value_set=pa.array(sorted(mids))),pc.and_(pc.equal(table['status'],'SUCCESS'),pc.equal(table['converged'],True)))
                    for row in table.filter(keep).to_pylist():by[row['molecule_id']].append(row)
                del index
            Q.need(stamp(os.fstat(stream.fileno()))==frame==stamp(path.lstat()),'OLD_SPRIME_SAME_FD_CURRENT_FRAME_AFTER_SELECTED_READ')
        frames.append({'reference':reference,'closed_whole_SHA_inherited_not_rehashed':True,'current_FD_frame':list(frame)})
    old_by={m:sorted((p for p in all_pairs if p['molecule_id']==m),key=lambda p:p['random_order_rank']) for m in mids}
    from workflows.data_v1_final.pprime.common import ordered_two,canonical
    for mid,rows in by.items():
        original=old_by[mid];first2=ordered_two(rows,mid,20261025)
        Q.need(len(rows)>=2 and [r['sprime_conf_idx'] for r in first2]==[p['conformer']['sprime_conf_idx'] for p in original],'SOURCE_FULL_FIXED_ORDER_FIRST2_UNCHANGED')
        for row,pair in zip(first2,original):Q.need(hashlib.sha256(canonical(row)).hexdigest()==pair['conformer_row_sha256'],'EXACT_ORIGINAL_SELECTED_ROW_SHA')
    return by,frames

def load_science(plan):
    """Use original loader and its two exact pins; isolate its historical import."""
    from workflows.data_v1_final.conformers.common import load_science as original_load
    recipe=C.meta(plan['original_sprime_recipe_reference']);pins=recipe['science_source_pins'];expected=pathlib.Path(pins[1]['path'])
    prior=sys.modules.get('prepare');Q.need(prior is None or pathlib.Path(prior.__file__).absolute()==expected,'NO_DIFFERENT_LEGACY_PREPARE_IMPORT')
    science=original_load(recipe);Q.need(pathlib.Path(science.__file__).absolute()==pathlib.Path(pins[0]['path'])
        and pathlib.Path(sys.modules['prepare'].__file__).absolute()==expected,'ACTUAL_ORIGINAL_SPRIME_IMPORT_BINDING')
    return science

def source_native(pair,rows,engine,science):
    import numpy as np
    original=engine.NATIVE.read_native(pair['source']);graph=engine.source_bond_graph(original['_source_raw'],original)
    Q.need(not graph['bond_graph_issues'] and graph['bond_pairs_zero_based'] is not None,'ACTUAL_SOURCE_BOND_GRAPH_REQUIRED_NO_GUESS')
    native,provenance=geometry.adapt_native(original,dict(pair,bond_pairs=graph['bond_pairs_zero_based']))
    mol,z,pm7xyz=science.graph(original['_source_raw']);Q.need(z.tolist()==original['z'].tolist(),'ORIGINAL_RMSD_MOLECULE_SAME_ATOM_ORDER')
    for row in rows:
        Q.need(row['molecule_id']==pair['molecule_id'] and row['atom_order_sha256']==original['native_atom_order_sha256'],'ALL_SELECTED_MID_SPRIME_ATOM_SHA')
        geometry.geometry_hash(z.tolist(),row['coordinates'])
    ordered_rows=[{'conformer_id':r['sprime_conf_idx'],'energy':r['uff_energy_kcal_mol'],'coordinates':r['coordinates']} for r in rows]
    orders=selection.conformer_orders(ordered_rows,lambda a,b:science.rmsd(mol,a['coordinates'],b['coordinates']),pair['molecule_id'],'uff_sprime',20261025)
    Q.need(orders['fixed_random'][0]==pair['conformer']['sprime_conf_idx'],'QA_CHOSEN_RANK0_OF_ORIGINAL_FULL_ORDER')
    return native,provenance,{'molecule_id':pair['molecule_id'],'orders':orders,'order_seed':20261025,'source':'uff_sprime',
        'order_scope':'ORIGINAL_SPRIME_SELECTED_MID_QA_PROVENANCE_NOT_FINAL_COMMON','source_conformer_count':len(rows),
        'geometry_SHA256_by_physical_id':{str(r['sprime_conf_idx']):geometry.geometry_hash(z.tolist(),r['coordinates']) for r in rows}}

def lmdb_frames(chosen,assets):
    """Closed authority hashes are inherited; selected payloads are rehashed by reader."""
    by_path={r['path']:r for r in assets};result=[]
    for name in sorted({p['source']['source_path'] for p in chosen}):
        Q.need(name in by_path,'SELECTED_LMDB_HAS_ORIGINAL_CLOSED_DATA_AUTHORITY')
        ref=C.O.triple(by_path[name]);path=pathlib.Path(name);Q.need(not any(v.is_symlink() for v in (path,*path.parents)),'SOURCE_LMDB_NON_SYMLINK')
        info=path.lstat();Q.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278 and info.st_size==ref['bytes'],'SELECTED_LMDB_CURRENT_SOURCE_FRAME')
        result.append({'reference':ref,'current_frame':list(stamp(info)),'whole_SHA_inherited_not_rehashed':True,'selected_payload_SHA_checked_by_original_reader':True})
    return result

def check_lmdb_frames(frames):
    for value in frames:Q.need(list(stamp(pathlib.Path(value['reference']['path']).lstat()))==value['current_frame'],'SOURCE_LMDB_FRAME_CHANGED_DURING_PAYLOAD_READS')

def render_one(pair,native,old,new,engine):
    """At most60 task bundles returned per MID, no program or source reader call."""
    import numpy as np
    from workflows.data_v1_final.pprime.vector_audit.math_v1 import rotation_case
    results=[];mid=pair['molecule_id'];row=copy.deepcopy(pair['source']);row.update(record_id=pair['record_id'],molecule_id=mid,geometry_source='uff_sprime')
    for before in old['tasks']:
        for arm in C.ARMS:
            transform=rotation_case(native['coords'],row['record_id'],before,old,'rotated' if arm=='R1' else 'base')
            supplied=dict(native,coords=np.asarray(transform['native_coordinates_A'],dtype='<f8'))
            original=engine.render_inputs(before,supplied,row,old)
            if arm.startswith('P'):original={n:T.p90(b,n) if n in ('input.xyz','input.mop') else b for n,b in original.items()}
            actual=T.arrays(original,native['symbols']);rotation=C.O.P90 if arm.startswith('P') else transform['rotation_matrix']
            case={'molecule_id':mid,'geometry_source':'uff_sprime','condition':before['name'],'calc_type':before['name'],'arm':arm,
                'row':row,'source_record':pair['source'],'symbols':list(native['symbols']),'atomic_numbers':native['z'].tolist(),
                'pairs':[list(v) for v in native['pairs']],'native_atom_order_sha256':native['native_atom_order_sha256'],
                'rotation_matrix':rotation,'actual_rendered_coordinates_A':actual.tolist(),'source_UFF_geometry_sha256':geometry.geometry_hash(native['z'].tolist(),native['coords'].tolist()),
                'source_UFF_coordinate_sha256':pair['uff_coordinate_sha256'],'clean_source_UFF_coordinates_A':native['coords'].tolist()}
            bridge,seed=T.bridge(case,original,before,old,engine)
            old_task={'original_task':before,'case':case,'seed':seed,'native_coordinates_A':bridge['coords'].tolist()}
            bridge,seed,after,candidate=targets(old_task,original,old,new,engine)
            Q.need(sum(map(len,candidate.values()))<=C.O.INPUT_CAP and set(original)==set(candidate),'BOUNDED_EXACT_FROZEN_INPUT_FILE_SET')
            Q.need(before['name'] in C.TASKS and np.array_equal(T.arrays(candidate,native['symbols']),actual),'CANDIDATE_INPUT_COORDINATE_BITS_IDENTICAL')
            results.append({'molecule_id':mid,'arm':arm,'condition':before['name'],'case':case,'seed':seed,'original_task':before,'candidate_task':after,
                'native_coordinates_A':bridge['coords'].tolist(),'original_inputs':original,'candidate_inputs':candidate})
    Q.need(len(results)==60,'EXACT12_TASKS_TIMES5_ARMS_PER_MID');return results
