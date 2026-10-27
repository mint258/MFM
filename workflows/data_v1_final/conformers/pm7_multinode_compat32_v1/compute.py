"""Only explicit local science context; original compute numerical body retained."""
import ast,hashlib,math,pathlib,time
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import contract as C,inheritance as H,core as ORIGINAL
geometry_orders=ORIGINAL.geometry_orders
unique_representatives=ORIGINAL.unique_representatives


def compute(task,science,journal=None):
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    started=time.monotonic();mid=task['meta']['molecule_id'];records=sorted(task['records'],key=lambda r:r['record_id'])
    C.need(len(records)==task['meta']['records']==len({r['record_id'] for r in records}),'ENTIRE_ORIGINAL_PM7_MOLECULE_REQUIRED')
    result={'schema':'PM7_INDEPENDENT_MOLECULE_CACHE_V1','molecule_id':mid,'cache_key':task['cache_key'],
        'source_population_authority':task['source_population_authority'],'PM7_source_count':len(records),'record_ids':[r['record_id'] for r in records],
        'source_records':records,'software_bound':task['software_bound'],'hof_mode':task['hof_mode'],'hof_by_record':task['hof'],
        'atomic_numbers':None,'pm7':[],'record_read_events':[],'source_errors':[],'orders':None,'unique_representatives':None,
        'status':'PENDING','Sprime_anchor_used':False,'native_energy_used_for_HOF_or_order':False,
        'new_UFF_calls':0,'new_QM_calls':0,'geometry_generation_or_optimization_calls':0,
        'common':False,'physical_int64_release':False,'full_cache_release':False}
    if task['software_bound']['status']!='WITHIN_SOFTWARE_BOUND':
        result.update(status=task['software_bound']['status'],records_attempted=0,records_not_read=len(records));return result
    mol=numbers=signature=None;pc=H.profile_common()
    for row in records:
        event={'record_id':row['record_id'],'status':'READ_ATTEMPTED'};result['record_read_events'].append(event)
        if journal is not None:journal(row['record_id'],'started',event)
        try:
            raw=science.read(row);other,z,coordinates=science.graph(raw);graph=science.ordered_graph(other)
            if mol is None:mol,numbers,signature=other,z,graph
            C.need(np.array_equal(numbers,z) and signature==graph,'FIXED_SOURCE_ATOM_SEQUENCE_OR_GRAPH_MISMATCH')
            C.need(len(z)==int(row['total_atoms']),'SOURCE_ATOM_COUNT_CHANGED')
            hof=task['hof'][row['record_id']];C.validate_hof(hof)
            result['pm7'].append({'conformer_id':row['record_id'],'coordinates':coordinates.tolist(),
                'energy':hof['value_kcal_mol'] if hof['valid'] else None,'geometry_sha256':pc.IO.geometry_sha(z,coordinates)})
            event.update(status='PAYLOAD_SHA_GRAPH_AND_GEOMETRY_VALIDATED',geometry_sha256=result['pm7'][-1]['geometry_sha256'])
        except Exception as exc:
            event.update(status='SOURCE_VALIDATION_FAILED',error=repr(exc)[:16000]);result['source_errors'].append(dict(event))
        if journal is not None:journal(row['record_id'],'finished',event)
    result.update(records_attempted=len(result['record_read_events']),records_not_read=0)
    if result['source_errors'] or len(result['pm7'])!=len(records):
        result.update(status='PENDING_SOURCE_VALIDATION_NO_RECORDS_DROPPED',elapsed_seconds=time.monotonic()-started)
        if numbers is not None:result['atomic_numbers']=numbers.tolist()
        return result
    result['atomic_numbers']=numbers.tolist();pm7=result['pm7'];index={r['conformer_id']:i for i,r in enumerate(pm7)}
    # Ordered pairs are evaluated independently with the original routine. Do
    # not assume floating-point SVD gives bitwise symmetric or exact-zero diagonal.
    distances=[[science.rmsd(mol,left['coordinates'],right['coordinates']) for right in pm7] for left in pm7]
    C.need(all(math.isfinite(v) and v>=0 for row in distances for v in row),'FINITE_ORIGINAL_RMSD_CACHE_REQUIRED')
    distance=lambda left,right:distances[index[left['conformer_id']]][index[right['conformer_id']]]
    orders=geometry_orders(pm7,distance,mid,'pm7');representatives=unique_representatives(pm7,orders['fixed_random'],distance)
    energies=[r['energy'] for r in pm7 if r['energy'] is not None]
    result.update(status='PM7_GEOMETRY_CACHE_COMPLETE_HOF_COMPLETE' if len(energies)==len(records) else 'PM7_GEOMETRY_CACHE_COMPLETE_HOF_PENDING',
        graph_sha256=C.sha(signature),atom_order_sha256=hashlib.sha256(numbers.astype('<i8').tobytes()).hexdigest(),
        graph_anchor_record_id=records[0]['record_id'],graph_anchor_policy='STABLE_FIRST_NATIVE_RECORD_ID_WITH_ALL_ORDERED_GRAPHS_EQUAL; NO_SPRIME_DEPENDENCY',
        stereo_authority_claimed=False,heavy_atoms=int(np.count_nonzero(numbers!=1)),
        rotatable_bonds=int(rdMolDescriptors.CalcNumRotatableBonds(Chem.RemoveHs(mol))),rings=int(mol.GetRingInfo().NumRings()),
        pm7_count=len(pm7),pm7_unique=len(representatives),pm7_duplicate_conformer_fraction=1-len(representatives)/len(pm7),
        orders=orders,unique_representatives=representatives,
        pair_rmsd_A=distances,pair_rmsd_record_ids=[r['conformer_id'] for r in pm7],actual_original_RMSD_calls=len(pm7)*len(pm7),
        hof_valid_count=len(energies),hof_range_complete=len(energies)==len(records),
        hof_range_kcal_mol=max(energies)-min(energies) if energies else None,
        elapsed_seconds=time.monotonic()-started)
    return result


def prove_context_text(old_text,new_text):
    def function(text):
        rows=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='compute']
        C.need(len(rows)==1,'ONE_SCIENTIFIC_COMPUTE_FUNCTION')
        node=rows[0];return node,''.join(text.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    old_node,old=function(old_text);new_node,new=function(new_text)
    C.need(old.count('SCIENCE.')==4 and old.count('def compute(task,journal=None):')==1,'EXACT4_CONTEXT_CALLS_AND_SIGNATURE')
    expected=old.replace('def compute(task,journal=None):','def compute(task,science,journal=None):').replace('SCIENCE.','science.')
    C.need(new==expected,'ONLY_EXPLICIT_LOCAL_SCIENCE_ARGUMENT_AND4_NAME_BINDINGS')
    restored=new.replace('def compute(task,science,journal=None):','def compute(task,journal=None):').replace('science.','SCIENCE.')
    C.need(restored==old and ast.dump(ast.parse(restored),include_attributes=False)==ast.dump(ast.parse(old),include_attributes=False),
        'SCIENTIFIC_FUNCTION_BYTES_AND_AST_INVERSE_MUST_BE_IDENTICAL')
    C.need(geometry_orders is ORIGINAL.geometry_orders and unique_representatives is ORIGINAL.unique_representatives,
        'ORIGINAL_ORDER_AND_UNIQUE_FUNCTION_OBJECTS')
    return {'status':'EXACT_COMPUTE_BYTES_AST_INVERSE_ONLY_EXPLICIT_LOCAL_CONTEXT',
        'original_compute_source':str(pathlib.Path(ORIGINAL.__file__).absolute()),'original_function_sha256':hashlib.sha256(old.encode()).hexdigest(),
        'adapted_function_sha256':hashlib.sha256(new.encode()).hexdigest(),'inverse_scientific_AST_and_bytes_equal':True,
        'only_adaptations':['science_argument','four_SCIENCE_attribute_roots_to_local_science'],
        'original_geometry_orders_and_unique_function_objects':True,'old_module_globals_assigned':False,
        'threshold_seed_reader_RMSD_HOF_or_selection_call_changed':False}


def inverse_proof():
    return prove_context_text(pathlib.Path(ORIGINAL.__file__).read_text(),pathlib.Path(__file__).read_text())
