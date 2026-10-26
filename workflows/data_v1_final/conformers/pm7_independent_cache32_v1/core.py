"""PM7-only native identity/geometry cache; never calls UFF/embedding/QM."""
from __future__ import annotations
import hashlib,json,math,os,pathlib,socket,sys,time
from . import contract as C,inheritance as H
SELECTION=H.profile_common().SELECTION
SCIENCE=SESSION=None


def unique_representatives(rows, fixed_random, distance, threshold=0.5):
    by_id = {row["conformer_id"]: row for row in rows}
    if len(by_id) != len(rows) or set(fixed_random) != set(by_id) or len(fixed_random) != len(rows):
        raise ValueError("D7_CONFORMER_IDS_OR_ORDER_NOT_A_PERMUTATION")
    selected = []
    for key in fixed_random:
        distances = [distance(by_id[key], by_id[old]) for old in selected]
        if any(not math.isfinite(value) for value in distances):
            raise ValueError("D7_NONFINITE_RMSD")
        if all(value >= threshold for value in distances):
            selected.append(key)
    return selected


def geometry_orders(rows, distance, molecule_id, source):
    random_order = sorted((row["conformer_id"] for row in rows),
        key=lambda key: (SELECTION.stable_key(20261025, molecule_id, source, key), str(key)))
    if all(row["energy"] is not None for row in rows):
        return {**SELECTION.conformer_orders(rows, distance, molecule_id, source, 20261025), "status": "COMPLETE"}
    return {"fixed_random": random_order, "energy": None, "diversity": None,
            "status": "ENERGY_AND_MIN_ENERGY_DIVERSITY_UNAVAILABLE_CANONICAL_HOF_MISSING"}


def worker_init(session):
    global SCIENCE,SESSION
    from . import io as I
    I.continuation(session);SESSION=session;pc=H.profile_common()
    SCIENCE=pc.IO.load_science({'science_source_pins':[C.SCIENCE_SOURCE,C.SCIENCE_PREPARE]});SCIENCE.worker_init()
    C.need(pathlib.Path(sys.modules['prepare'].__file__).absolute()==pathlib.Path(C.SCIENCE_PREPARE['path']),
        'ORIGINAL_READER_PREPARE_IMPORT_LOCATOR_MUST_MATCH_PIN')
    import torch
    torch.set_num_threads(1)
    if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
    from rdkit import rdBase
    C.need(pc.IO.version_tuple(rdBase.rdkitVersion)==(2025,9,5),'EXACT_ORIGINAL_RDKIT2025_09_5')


def compute(task,journal=None):
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
            raw=SCIENCE.read(row);other,z,coordinates=SCIENCE.graph(raw);graph=SCIENCE.ordered_graph(other)
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
    distances=[[SCIENCE.rmsd(mol,left['coordinates'],right['coordinates']) for right in pm7] for left in pm7]
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


def one(item):
    from . import io as I
    I.continuation(SESSION);task,reference=item;out=pathlib.Path(SESSION['output_root']);key=task['cache_key']
    runtime={'job_id':SESSION['job_id'],'uid':os.getuid(),'node':socket.gethostname().split('.')[0],'pid':os.getpid(),
        'start_ticks':I.R.proc_ticks(os.getpid()),'boot_id':SESSION['boot_id'],'parent_pid':os.getppid()}
    start=I.json_new(out/'starts'/(key+'.json'),{'schema':'PM7_CACHE_READONLY_WORKER_STARTED_V1','task_reference':reference,
        'cache_key':key,'molecule_id':task['meta']['molecule_id'],'runtime':runtime},out)
    def journal(rid,phase,event):
        name=key+'_'+hashlib.sha256(rid.encode()).hexdigest()+'_'+phase+'.json'
        I.json_new(out/'record_events'/name,{'cache_key':key,'task_reference':reference,'runtime':runtime,'record_event':event},out)
    try:result=compute(task,journal)
    except Exception as exc:
        result={'schema':'PM7_INDEPENDENT_MOLECULE_CACHE_V1','molecule_id':task['meta']['molecule_id'],'cache_key':key,
            'status':'PENDING_UNKNOWN_WORKER_FAILURE','error':repr(exc)[:16000],'pm7':[],'source_errors':[repr(exc)[:16000]],
            'new_UFF_calls':0,'new_QM_calls':0,'common':False}
    result.update(runtime=runtime,worker_start_reference=start,task_reference=reference)
    packet=I.packet(out/'molecules'/(key+'.json.gz'),result,out)
    finished=I.json_new(out/'finished'/(key+'.json'),{'packet_reference':packet,'worker_start_reference':start,
        'cache_key':key,'molecule_id':task['meta']['molecule_id'],'status':result['status'],'runtime':runtime},out)
    return {'packet_reference':packet,'finished_reference':finished,'worker_start_reference':start,'cache_key':key,
        'molecule_id':task['meta']['molecule_id'],'status':result['status'],'runtime':runtime}
