"""Readonly PM7 and D7 under an explicit actual analysis-day worker context."""
import gzip,hashlib,json,math,os,pathlib,time,traceback
from . import contract as C,io as I
from .math_bridge import geometry_orders,unique_representatives,pm7_compute
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import inheritance as H,contract as PC
SCIENCE=CONTEXT=None
IO=H.profile_common().IO

def initialize(context):
    global SCIENCE,CONTEXT
    CONTEXT=context;I.identity(context['proof']);pc=H.profile_common()
    SCIENCE=pc.IO.load_science({'science_source_pins':[PC.SCIENCE_SOURCE,PC.SCIENCE_PREPARE]});SCIENCE.worker_init()
    import torch
    torch.set_num_threads(1)
    if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
    from rdkit import rdBase
    C.need(pc.IO.version_tuple(rdBase.rdkitVersion)==(2025,9,5),'EXACT_UNCHANGED_NATIVE_GRAPH_RMSD_VERSION')

def d7(task,cache,science):
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    started, mid = time.monotonic(), task["meta"]["molecule_id"]
    records, sprime = task["records"], sorted(task["sprime"], key=lambda row: row["sprime_conf_idx"])
    if len(records) != task["meta"]["S_conformers"] or len(sprime) != task["meta"]["Sprime_conformers"]:
        raise ValueError("D7_COMPLETE_MOLECULE_COUNT_MISMATCH")
    if len({row["record_id"] for row in records}) != len(records) or len({row["sprime_conf_idx"] for row in sprime}) != len(sprime):
        raise ValueError("D7_DUPLICATE_CONFORMER_ID")
    anchors = {row["source_record_id"] for row in sprime}
    by_record = {row["record_id"]: row for row in records}
    if len(anchors) != 1 or not anchors <= set(by_record):
        raise ValueError("D7_SPRIME_SOURCE_ANCHOR_MAPPING_MISMATCH")
    anchor = science.read(by_record[next(iter(anchors))])
    mol, numbers, _ = science.graph(anchor)
    graph_signature = science.ordered_graph(mol)
    graph_sha = hashlib.sha256(json.dumps(graph_signature, separators=(",",":")).encode()).hexdigest()
    atom_sha = hashlib.sha256(numbers.astype("<i8").tobytes()).hexdigest()
    stereo_source, stereo_signature = science.fix_stereo(mol, str(science.field(anchor, "smiles")))
    pm7, uff = [], []
    cached={row['conformer_id']:row for row in cache['pm7']}
    C.need(set(cached)==set(by_record) and cache['atomic_numbers']==numbers.tolist()
      and cache['atom_order_sha256']==atom_sha and cache['graph_sha256']==C.F.sha_value(graph_signature),
      'EXACT_ALREADY_VALIDATED_PM7_NATIVE_RECORD_GRAPH_ATOMS')
    for rid in sorted(cached):
        row=cached[rid];hof=task['hof'][rid]
        C.need(IO.geometry_sha(numbers,row['coordinates'])==row['geometry_sha256']
          and row['energy']==(hof['value_kcal_mol'] if hof['valid'] else None),'EXACT_CACHED_FLOAT64_GEOMETRY_AND_CANONICAL_HOF')
        pm7.append(row)
    for row in sprime:
        coordinates = np.asarray(row["coordinates"], dtype=np.float64)
        geometry_sha = IO.geometry_sha(numbers, coordinates)
        if row["status"] != "SUCCESS" or row["converged"] is not True or row["atom_order_sha256"] != atom_sha or row["stereo_signature"] != stereo_signature:
            raise ValueError("D7_ACCEPTED_SPRIME_STATUS_ATOMS_OR_STEREO_MISMATCH")
        conformer = Chem.Conformer(len(numbers))
        for index, xyz in enumerate(coordinates):
            conformer.SetAtomPosition(index, xyz.tolist())
        conformer.Set3D(True)
        cid = mol.AddConformer(conformer, assignId=True)
        valid_stereo = science.check_geometry_stereo(mol, cid)
        mol.RemoveConformer(cid)
        if not valid_stereo:
            raise ValueError("D7_SPRIME_GEOMETRIC_STEREO_CHECK_FAILED")
        energy = float(row["uff_energy_kcal_mol"])
        if not np.isfinite(energy):
            raise ValueError("D7_SPRIME_NONFINITE_ENERGY")
        uff.append({"conformer_id": int(row["sprime_conf_idx"]), "coordinates": coordinates.tolist(),
                    "energy": energy, "geometry_sha256": geometry_sha})
    distance = lambda left, right: science.rmsd(mol, left["coordinates"], right["coordinates"])
    orders = {"pm7": cache['orders'],
              "uff_sprime": geometry_orders(uff, distance, mid, "uff_sprime")}
    unique = {"pm7": cache['unique_representatives'],
              "uff_sprime": unique_representatives(uff, orders["uff_sprime"]["fixed_random"], distance)}
    cross = [[distance(left, right) for right in uff] for left in pm7]
    hof_values = [row["energy"] for row in pm7 if row["energy"] is not None]
    return {"status": "D7_MOLECULE_PROFILE_COMPLETE", "molecule_id": mid,
            "source_role": task["meta"]["split_role"], "population_scope": "ORIGINAL_SOURCE_PRECOMMON_PROFILE",
            "pm7_count": len(pm7), "uff_sprime_count": len(uff),
            "pm7_unique": len(unique["pm7"]), "uff_sprime_unique": len(unique["uff_sprime"]),
            "pm7_duplicate_conformer_fraction": 1 - len(unique["pm7"]) / len(pm7),
            "heavy_atoms": int(np.count_nonzero(numbers != 1)),
            "rotatable_bonds": int(rdMolDescriptors.CalcNumRotatableBonds(Chem.RemoveHs(mol))),
            "rings": int(mol.GetRingInfo().NumRings()),
            "hof_valid_count": len(hof_values), "hof_total_count": len(pm7),
            "hof_range_kcal_mol": max(hof_values) - min(hof_values) if hof_values else None,
            "hof_range_complete": len(hof_values) == len(pm7), "hof_by_record": task["hof"],
            "cross_rmsd_A": cross, "cross_pm7_ids": [row["conformer_id"] for row in pm7],
            "cross_uff_sprime_ids": [row["conformer_id"] for row in uff],
            "orders": orders, "unique_representatives": unique,
            "unique_greedy_order": "fixed_random_same_algorithm_both_sources",
            "atom_order_sha256": atom_sha, "graph_sha256": graph_sha,
            "stereo_source": stereo_source, "stereo_signature": stereo_signature,
            "geometry_hashes": {source: {str(row["conformer_id"]): row["geometry_sha256"] for row in rows}
                                for source, rows in (("pm7",pm7),("uff_sprime",uff))},
            "elapsed_seconds": time.monotonic() - started,
            "geometry_generation_calls": 0, "original_data_modified": False}


def one(task,prior_cache,d7_task,output,claim_reference):
    I.identity(CONTEXT['proof']);mid=task['meta']['molecule_id'];events=[]
    root=pathlib.Path(output).parent.parent;key=pathlib.Path(output).name[:-8]
    start={'claim_reference':claim_reference,'molecule_id':mid,'job_id':str(CONTEXT['proof']['job_id']),'uid':os.getuid(),
      'node':CONTEXT['proof']['request']['node'],'boot_id':CONTEXT['proof']['boot_id'],'pid':os.getpid(),'pid_start_ticks':I.PIO.ticks(os.getpid())}
    start_ref=I.save(root/'starts'/(key+'.json'),start)
    progress=root/'progress'/(key+'.jsonl');I.PIO.exclusive(progress,b'')
    def journal(rid,phase,event):
        item={'record_id':rid,'phase':phase,'event':event};events.append(item)
        fd=os.open(progress,os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW)
        with os.fdopen(fd,'ab') as f:f.write(C.canonical(item)+b'\n');f.flush();os.fsync(f.fileno())
    result={'molecule_id':mid,'PM7_source_count':len(task['records']),'common':d7_task is not None,'runtime':{
      'job_id':str(CONTEXT['proof']['job_id']),'uid':os.getuid(),'node':CONTEXT['proof']['request']['node'],'pid':os.getpid()},
      'new_UFF_calls':0,'new_QM_calls':0,'production_once_written':False,'claim_reference':claim_reference,'worker_start_reference':start_ref,
      'source_role':task['meta'].get('split_role'),'effective_role':task['meta'].get('effective_role')}
    try:
        cache=prior_cache if prior_cache is not None else pm7_compute(task,SCIENCE,journal)
        result['cache']=cache;result['cache_origin']='IMPORTED_REAL_CLOSED_CACHE' if prior_cache is not None else 'NEW_READONLY_CACHE'
        result['d7']=d7(d7_task,cache,SCIENCE) if d7_task is not None and cache['status'].startswith('PM7_GEOMETRY_CACHE_COMPLETE') else None
        result['status']='DURABLE_READONLY_MOLECULE_RESULT'
    except BaseException as exc:result.update(status='READONLY_MOLECULE_UNKNOWN',error=repr(exc),traceback=traceback.format_exc())
    result['record_progress']=events
    raw=C.canonical(result);C.need(len(raw)<=256<<20,'EXPLICIT_WHOLE_MOLECULE_PACKET_BOUND')
    ref=I.PIO.exclusive(pathlib.Path(output),gzip.compress(raw,mtime=0))
    actual=json.loads(gzip.decompress(I.verify(ref).read_bytes()));C.need(actual==result,'FULL_FLOAT64_PACKET_REOPEN_NOT_ONLY_RETURN_STATUS')
    return {'molecule_id':mid,'packet_reference':ref,'status':result['status'],'cache_origin':result.get('cache_origin'),
      'geometry_status':result.get('cache',{}).get('status'),'d7_closed':result.get('d7') is not None,'runtime':result['runtime']}
