"""Real N1 second-UFF kernel, no standalone runner, submitter or automatic retry."""
from __future__ import annotations
import copy,hashlib,json,os,pathlib,socket,sys,time,traceback
from . import contract as C

sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).absolute().parent
CTX={}


def worker_init(catalog_reference,source_population_authority_reference,prepared_manifest_reference,admission):
    """Initializer for Root's central-v2 admitted finite source-wave parent runner.

    admission is an actual binding supplied by that runner: proof_path,
    execution_argv and runner_source reference. No future proof/authority is
    generated here. Fresh admission is consumed by the actual primary entry;
    workers bind its still-live validated parent/allocation continuation.
    """
    global CTX
    CTX={};catalog=C.load_catalog(catalog_reference);refs=catalog['references']
    C.reference_shape(source_population_authority_reference);C.reference_shape(prepared_manifest_reference)
    from . import io as I
    local_refs=[]
    for name in I.FILES:
        path=HERE/name;body=path.read_bytes()
        local_refs.append({'path':str(path),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
    proof=I.active_parent_continuation(admission,C.SCOPE_KEY,C.SCOPE,'conformer')
    I.authorized(proof,(catalog_reference,source_population_authority_reference,prepared_manifest_reference,
        *local_refs,*refs.values(),*catalog['inherited_v1_sources']))
    C.need(proof['request']['pilot'] is False and proof['request']['scope']['mode']=='FULL_SOURCE_AFTER_PROFILE',
        'ONLY_ROOT_REVIEWED_BOUNDED_SOURCE_WAVE_ADMITTED_NOT_PILOT_OR_FIXTURE')
    os.environ.update({name:'1' for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    io=C.module_from_pin('_n1_pprime2_frozen_io',refs['io'])
    selection=C.module_from_pin('_n1_pprime2_frozen_selection',refs['selection'])
    recipe=io.load_config(C.pinned_small(refs['recipe']))
    C.need(recipe['science_source_pins']==[refs['graph_stereo_rmsd'],refs['legacy_prepare_import']],
        'EXACT_ORIGINAL_GRAPH_STEREO_RMSD_IMPORT_CHAIN_REQUIRED')
    proposal=json.loads(C.pinned_small(refs['proposal_config_reference_only']).read_text())
    C.need(proposal['proposed_seed_domain']==C.SEED_DOMAIN and proposal['source_N_remains']==1
        and proposal['candidate_multiplier_of_original_N']==10 and proposal['max_candidates']==300,
        'ORIGINAL_PROPOSAL_SEED_AND_SOURCE_N1_RECIPE_REQUIRED')
    if 'prepare' in sys.modules:
        C.need(pathlib.Path(sys.modules['prepare'].__file__).absolute()==pathlib.Path(refs['legacy_prepare_import']['path']),
            'WRONG_LEGACY_PREPARE_MODULE_ALREADY_IMPORTED')
    science=io.load_science(recipe)
    C.need(pathlib.Path(sys.modules['prepare'].__file__).absolute()==pathlib.Path(refs['legacy_prepare_import']['path']),
        'ACTUAL_LEGACY_PREPARE_IMPORT_LOCATION_DIFFERS')
    science.worker_init()
    import torch
    torch.set_num_threads(1)
    if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)
    from rdkit import rdBase
    C.need(io.version_tuple(rdBase.rdkitVersion)==io.version_tuple('2025.09.5'),'EXACT_RDKIT2025_09_5_REQUIRED')
    proof_ref=io.reference(admission['proof_path'])
    stat=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    CTX={'io':io,'science':science,'selection':selection,'recipe':recipe,'catalog_reference':catalog_reference,
        'source_population_authority_reference':source_population_authority_reference,'prepared_manifest_reference':prepared_manifest_reference,
        'checkpoint_output_root':admission['output_root'],
        'frozen_references':refs,'startup_proof_reference':proof_ref,
        'runtime':{'job_id':str(proof['job_id']),'uid':os.getuid(),'node':socket.gethostname().split('.')[0],
            'pid':os.getpid(),'start_ticks':int(stat[19]),'boot_id':proof['boot_id'],
            'allocated_cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','memory_requested':False,
            'rdkit_version':rdBase.rdkitVersion,'seed_domain':C.SEED_DOMAIN}}


def _add_conformer(mol,coordinates):
    # Same direct atom-index insertion used by the frozen fill adapter.
    from rdkit import Chem
    conf=Chem.Conformer(mol.GetNumAtoms())
    for index,xyz in enumerate(coordinates):conf.SetAtomPosition(index,list(map(float,xyz)))
    conf.Set3D(True);return mol.AddConformer(conf,assignId=True)


def _raw_number(value,np):
    value=float(value)
    return value if np.isfinite(value) else 'NaN' if np.isnan(value) else '+Infinity' if value>0 else '-Infinity'


def _embedding(mol,allchem,requested,seed,attempts):
    params=allchem.ETKDGv3();params.randomSeed=seed;params.numThreads=1
    params.enforceChirality=True;params.pruneRmsThresh=-1.;params.maxIterations=200
    params.useRandomCoords=False
    def call():
        event={'seed':seed,'numConfs':requested,'numThreads':1,'enforceChirality':True,
            'pruneRmsThresh':-1.,'maxIterations':200,'useRandomCoords':bool(params.useRandomCoords),
            'returned_ids':None,'error':None,'started_unix':time.time()}
        started=time.monotonic();attempts.append(event)
        try:
            ids=list(allchem.EmbedMultipleConfs(mol,numConfs=requested,params=params))
            event['returned_ids']=[int(cid) for cid in ids];return ids
        except Exception as exc:
            event.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc());raise
        finally:event['elapsed_seconds']=time.monotonic()-started
    try:ids=call()
    except (RuntimeError,ValueError):ids=[]
    # Only the original zero-return random-coordinate fallback, same seed/10.
    # Partial nonempty embedding is not expanded or retried.
    if not ids:params.useRandomCoords=True;ids=call()
    C.need(ids,'EMBED_FAILED')
    C.need(len(ids)<=requested and len(ids)==len(set(ids))
        and all(type(cid) is int and cid>=0 for cid in ids),'INVALID_NATIVE_EMBEDDED_CANDIDATE_IDS')
    return ids


def process_task(task):
    """Return one new packet; Root must claim once and persist it durably.

    Reads exactly one original PM7 payload via the frozen reader. A selected
    second geometry can only originate in this invocation's native optimizer
    events; the accepted baseline is never put into the generated candidate list.
    """
    C.need(CTX,'FRESH_ADMITTED_WORKER_INITIALIZATION_REQUIRED')
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import AllChem,rdMolDescriptors,rdtrajectory  # trajectory binding registration
    io,science,selection=CTX['io'],CTX['science'],CTX['selection']
    from . import io as I
    started=time.monotonic();events=[];embedding=I.EmbeddingJournal(CTX['checkpoint_output_root'],task);baseline_original=None;baseline_identity=None
    extra=None;orders=None;baseline_valid=False
    summary={'molecule_id':task.get('meta',{}).get('molecule_id'),'status':'UNPROCESSED','error':None,
        'source_N_required':1,'PM7_source_count':0,'original_Sprime_count_required':1,'UFF_desired_count':2,
        'input_PM7_pointer_count':len(task.get('records',[])) if isinstance(task.get('records',[]),list) else None,
        'candidate_requested':0,'candidate_embedded':0,'optimizer_calls_attempted':0,'optimizer_calls_finished':0,
        'finite_converged_stereo_candidates':0,'eligible_new_geometry_candidates':0,
        'Pprime_actual_records':0,'selected_unique_at_0p5_A':0,'candidate_pool_unique_at_0p5_A':0,
        'below_dedup_threshold':False,'automatic_retry':False,'new_QM_calls':0,
        'old_source_or_common_counts_modified':False,'new_population_membership_released':False}
    try:
        meta,pointer,baseline_original,seed=C.validate_task(task,CTX['source_population_authority_reference'])
        mid=meta['molecule_id'];summary.update(PM7_source_count=1,seed=seed,effective_role=meta['effective_role'])
        raw=science.read(pointer)
        energy_field=science.field(raw,'energy')
        C.need(energy_field is not None and np.isfinite(float(science.plain(energy_field).reshape(-1)[0])),
            'PM7_MINIMUM_ENERGY_MISSING')
        mol,numbers,pm7_xyz=science.graph(raw)
        ordered_graph=science.ordered_graph(mol)
        atom_sha=hashlib.sha256(numbers.astype('<i8').tobytes()).hexdigest()
        stereo_source,signature=science.fix_stereo(mol,str(science.field(raw,'smiles')))
        summary.update(source_record_id=pointer['record_id'],atom_order_sha256=atom_sha,
            stereo_source=stereo_source,stereo_signature=signature,
            heavy_atoms=int(np.count_nonzero(numbers!=1)),
            rotatable_bonds=int(rdMolDescriptors.CalcNumRotatableBonds(Chem.RemoveHs(mol))),
            rings=int(mol.GetRingInfo().NumRings()))
        C.need(AllChem.UFFHasAllMoleculeParams(mol),'UFF_UNSUPPORTED')
        old=baseline_original;xyz=np.asarray(old['coordinates'],dtype=np.float64)
        baseline_sha=io.geometry_sha(numbers,xyz)
        C.need(old['atom_order_sha256']==atom_sha and old['source_record_id']==pointer['record_id'],
            'ACTUAL_RECORD_MANIFEST_MISMATCH:baseline_atom_or_anchor')
        C.need(old['stereo_signature']==signature,'ACTUAL_RECORD_MANIFEST_MISMATCH:baseline_stereo_signature')
        C.need(old.get('geometry_sha256',baseline_sha)==baseline_sha,'ACTUAL_RECORD_MANIFEST_MISMATCH:baseline_geometry_SHA')
        cid=_add_conformer(mol,xyz)
        try:C.need(science.check_geometry_stereo(mol,cid),'ACTUAL_RECORD_MANIFEST_MISMATCH:baseline_geometry_stereo')
        finally:mol.RemoveConformer(cid)
        energy=float(old['uff_energy_kcal_mol']);C.need(np.isfinite(energy),'ACTUAL_RECORD_MANIFEST_MISMATCH:baseline_energy')
        baseline={'candidate_key':'existing:000000','candidate_id':None,'coordinates':xyz.tolist(),'energy':energy,
            'seed':old['seed'],'origin':'accepted_sprime','geometry_sha256':baseline_sha}
        baseline_identity={'geometry_id':task['baseline_geometry_id'],'geometry_sha256':baseline_sha,
            'full_original_row_sha256':C.sha_value(old),'original_sprime_conf_idx':0,'unchanged':True}
        baseline_valid=True;summary.update(Pprime_actual_records=1,selected_unique_at_0p5_A=1,candidate_pool_unique_at_0p5_A=1)
        requested=min(CTX['recipe']['candidate_multiplier']*C.SOURCE_N,CTX['recipe']['max_candidates'])
        C.need(requested==10,'ORIGINAL_N1_REQUIRES10_NOT20_CANDIDATES')
        summary['candidate_requested']=requested;mol.RemoveAllConformers()
        try:ids=_embedding(mol,AllChem,requested,seed,embedding)
        finally:embedding.flush_last()
        summary['candidate_embedded']=len(ids)
        for cid in ids:
            event={'candidate_key':f'n1p2:{seed}:{cid:06d}','candidate_id':int(cid),'seed':seed,
                'origin':'data_v1_n1_pprime2','optimizer_called':False,'optimization_finished':False,
                'optimizer_code':None,'trajectory_snapshots':None,'finite':False,'stereo_valid':False,
                'geometry_readback_finished':False,
                'coordinates':None,'energy':None,'geometry_sha256':None,'error':None,
                'source_record_id':pointer['record_id'],'atom_order_sha256':atom_sha,
                'iteration_limit':2000,'energyTol':1e-6,'forceTol':1e-4,'snapshotFreq':1,
                'started_unix':time.time()}
            events.append(event);candidate_started=time.monotonic()
            I.event_checkpoint(CTX['checkpoint_output_root'],task,'candidate_%06d_started'%cid,event)
            try:
                forcefield=AllChem.UFFGetMoleculeForceField(mol,confId=cid)
                C.need(forcefield is not None and callable(getattr(forcefield,'MinimizeTrajectory',None)),
                    'NATIVE_UFF_FORCEFIELD_OR_OPTIMIZER_UNAVAILABLE')
                I.event_checkpoint(CTX['checkpoint_output_root'],task,'candidate_%06d_minimize_intent'%cid,
                    {'native_call_intent':True,'event':event})
                event['optimizer_called']=True;summary['optimizer_calls_attempted']+=1
                code,trajectory=forcefield.MinimizeTrajectory(snapshotFreq=1,maxIts=2000,energyTol=1e-6,forceTol=1e-4)
                event['optimization_finished']=True
                summary['optimizer_calls_finished']+=1
                event.update(optimizer_code=int(code),trajectory_snapshots=len(trajectory))
                current=np.asarray(mol.GetConformer(cid).GetPositions(),dtype=np.float64)
                energy=float(forcefield.CalcEnergy());finite=bool(np.isfinite(current).all() and np.isfinite(energy))
                C.need(science.ordered_graph(mol)==ordered_graph and
                    [atom.GetAtomicNum() for atom in mol.GetAtoms()]==numbers.tolist(),'GENERATED_GRAPH_OR_ATOM_ORDER_CHANGED')
                stereo_ok=finite and science.check_geometry_stereo(mol,cid)
                event.update(coordinates=current.tolist() if finite else [[_raw_number(v,np) for v in row] for row in current],
                    energy=_raw_number(energy,np),finite=finite,stereo_valid=bool(stereo_ok),
                    geometry_sha256=io.geometry_sha(numbers,current) if finite else None,geometry_readback_finished=True)
                if finite and stereo_ok and code==0:summary['finite_converged_stereo_candidates']+=1
            except Exception as exc:
                event.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc());raise
            finally:
                event['elapsed_seconds']=time.monotonic()-candidate_started
                I.event_checkpoint(CTX['checkpoint_output_root'],task,'candidate_%06d_observed'%cid,event)
        distance=lambda left,right:science.rmsd(mol,left['coordinates'],right['coordinates'])
        chosen=C.select_real_second(mid,baseline,events,distance,selection)
        summary.update(status=chosen['status'],eligible_new_geometry_candidates=chosen['eligible_geometry_candidates'],
            Pprime_actual_records=chosen['Pprime_actual_records'],selected_unique_at_0p5_A=chosen['selected_unique_at_0p5_A'],
            candidate_pool_unique_at_0p5_A=chosen['candidate_pool_unique_at_0p5_A'],
            candidate_identity_or_quality_exclusions=chosen['identity_or_quality_exclusions'])
        second=chosen['second']
        if second is not None:
            native_id=f"n1p2:{seed}:{second['candidate_id']}"
            identity={'molecule_id':mid,'native_extra_conformer_id':native_id,'geometry_sha256':second['geometry_sha256']}
            geometry_id='uff_sprime_n1_pprime2:'+C.sha_value(identity)
            rmsd_pm7=science.rmsd(mol,second['coordinates'],pm7_xyz)
            extra={'molecule_id':mid,'native_extra_conformer_id':native_id,'geometry_id':geometry_id,
                'geometry_source':'uff_sprime','supplement_role':'pprime_n1_second','status':'SUCCESS','converged':True,
                'atomic_numbers':numbers.tolist(),'coordinates':second['coordinates'],'uff_energy_kcal_mol':second['energy'],
                'seed':seed,'candidate_id':second['candidate_id'],'optimizer_code':second['optimizer_code'],
                'trajectory_snapshots':second['trajectory_snapshots'],'iterations':second['trajectory_snapshots'],
                'geometry_sha256':second['geometry_sha256'],'source_record_id':pointer['record_id'],
                'atom_order_sha256':atom_sha,'stereo_source':stereo_source,'stereo_signature':signature,
                'baseline_geometry_id':task['baseline_geometry_id'],'baseline_geometry_sha256':baseline_sha,
                'origin':'data_v1_n1_pprime2','original_N':1,'baseline_count':1,'UFF_desired_count':2,
                'below_dedup_threshold':second['below_dedup_threshold'],
                'min_rmsd_to_previously_selected_A':second['min_rmsd_to_previously_selected_A'],
                'nearest_pm7_record_id':pointer['record_id'],'nearest_pm7_rmsd_A':rmsd_pm7,
                'optimizer_event_key':second['candidate_key']}
            orders=C.expanded_orders(mid,baseline,second,distance,selection)
            summary['below_dedup_threshold']=second['below_dedup_threshold']
        C.need(C.sha_value(baseline_original)==task['baseline_row_sha256'],'ORIGINAL_BASELINE_MUTATED')
    except Exception as exc:
        # Any technical/source error preserves the actual event prefix, pending.
        # No implicit retry, seed expansion or alternative scientific recipe.
        extra=None;orders=None
        summary.update(status='PPRIME2_PENDING_GENERATION_OR_INPUT_FAILURE',error=type(exc).__name__+': '+str(exc),
            traceback=traceback.format_exc(),Pprime_actual_records=1 if baseline_valid else 0,
            selected_unique_at_0p5_A=1 if baseline_valid else 0,below_dedup_threshold=False)
        I.event_checkpoint(CTX['checkpoint_output_root'],task,'task_failure',{'summary':summary,'candidate_events':events,'embedding_calls':embedding})
    finally:
        summary.update(elapsed_seconds=time.monotonic()-started,
            embedding_calls_attempted=len(embedding),
            embedding_numConfs_requested_across_calls=sum(row['numConfs'] for row in embedding),
            observed_embedding_returned_count=sum(len(row['returned_ids']) for row in embedding if row['returned_ids'] is not None),
            embedding_calls_without_returned_ids=sum(row['returned_ids'] is None for row in embedding),
            candidate_nonconverged=sum(row['optimizer_code'] is not None and row['optimizer_code']!=0 for row in events),
            candidate_nonfinite=sum(row['geometry_readback_finished'] and not row['finite'] for row in events),
            candidate_stereo_rejected=sum(row['geometry_readback_finished'] and row['finite'] and not row['stereo_valid'] for row in events))
    return {'schema':'N1_PPRIME2_PILOT_GENERATION_PACKET_V2','summary':summary,
        'task_key':task.get('task_key'),'prepared_manifest_reference':CTX['prepared_manifest_reference'],
        'source_population_authority_reference':CTX['source_population_authority_reference'],
        'final_common_reference':None,'common':False,'pilot_membership':False,'production_membership':False,
        'catalog_reference':CTX['catalog_reference'],
        'startup_proof_reference':CTX['startup_proof_reference'],'runtime':copy.deepcopy(CTX['runtime']),
        'authority_references':copy.deepcopy(task.get('authority_references',{})),
        'baseline_original_row':copy.deepcopy(baseline_original),'baseline_identity':baseline_identity,
        'supplement':extra,'expanded_view':{'view_id':'pprime_parent_expanded_v1',
            'status':'TWO_REAL_PARENT_RECORDS_AVAILABLE' if extra else 'PENDING_SECOND_REAL_GEOMETRY',
            'baseline_reference':task.get('baseline_geometry_id'),'supplement_reference':extra['geometry_id'] if extra else None,
            'geometry_source':'uff_sprime','order_seed':20261025,'orders':orders},
        'embedding_calls':list(embedding),'candidate_optimizer_events':events,'all_actual_candidate_events_retained':True,
        'actual_parent_allocated_core_seconds':None,'actual_terminal_accounting_required':True,
        'original_PM7_pointer_count_changed':False,'original_Sprime_count_changed':False,'common_membership_changed':False}
