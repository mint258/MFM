"""Main-original packet IO; independent original physical functions, no optimizer."""
import hashlib,pathlib,types,traceback
from portable_n1_source_remaining_v1 import contract as C
from portable_n1_source_physical_qa_v1 import qa as ORIGINAL,identity as ID
from workflows.data_v1_final.pprime.n1_extra_common_day_v3 import history as H
CTX=CONTINUE=None


def initialize(context):
    global CTX,CONTINUE
    CTX=dict(context)
    CONTINUE=types.FunctionType(ORIGINAL.continuation.__code__,dict(ORIGINAL.continuation.__globals__,CTX=CTX),
        ORIGINAL.continuation.__name__,ORIGINAL.continuation.__defaults__,ORIGINAL.continuation.__closure__)
    C.need(CONTINUE.__code__ is ORIGINAL.continuation.__code__,'EXACT_ORIGINAL_PARENT_CONTINUATION_CODE')
    CONTINUE()
    io,science,selection,recipe,version=ORIGINAL.load_science(context['plan'])
    CTX.update(original_io=io,science=science,selection=selection,rdkit_version=version)


def one(item):
    entry,info=item;CONTINUE();job=entry['origin_job_id']
    result=dict(task_key=entry['task_key'],molecule_id=entry['molecule_id'],accepted=None,
        status='MAIN_ORIGINAL_PHYSICAL_QA_UNRESOLVED_NO_REGISTRATION',native_uid=1278,
        native_endpoint='202.38.247.57:22',native_parent_job_id=job,
        physical_QA_parent_job_id=CTX['parent']['job_id'],new_UFF_calls=0,new_QM_calls=0,automatic_retry=False)
    try:
        import numpy as np
        task=C.load(entry['task_reference'],8<<20)
        packet=H.packet(entry['packet_reference'],task,job)
        C.need(task['task_key']==entry['task_key'] and task['meta']['molecule_id']==entry['molecule_id']
            and packet['supplement'] is not None,'ACTUAL_ORIGINAL_MAIN_SELECTED_PACKET')
        origin=C.load(entry['origin_startup_proof_reference'])
        C.need(str(origin['job_id'])==str(job) and origin['uid']==1278 and origin['node']=='compute-0-13'
            and origin['execution_admission_granted'] is True and origin['request']['kind']=='conformer'
            and origin['request']['cpus']==16 and packet['startup_proof_reference']==entry['origin_startup_proof_reference'],
            'REAL_MAIN13_ORIGINAL_PARENT_NOT_ALPHA_IMPORT_OR_NEW_QA_ID')
        io,science=CTX['original_io'],CTX['science']
        evidence=C.load(task['authority_references']['accepted_baseline_evidence'],8<<20)
        old,extra,pointer=task['existing_conformers'][0],packet['supplement'],task['records'][0]
        C.need(evidence['original_row']==old and evidence['source_population_authority']==task['authority_references']['source_population_authority'],
            'ORIGINAL_TASK_BASELINE_AUTHORITY_NOT_A_NEW_INPUT_ALIAS')
        raw=science.read(pointer);energy=science.field(raw,'energy')
        C.need(energy is not None and np.isfinite(float(science.plain(energy).reshape(-1)[0])),'ORIGINAL_PM7_MINIMUM_ENERGY_REQUIRED')
        mol,numbers,pm7_xyz=science.graph(raw);graph=science.ordered_graph(mol)
        source,signature=science.fix_stereo(mol,str(science.field(raw,'smiles')))
        atom=hashlib.sha256(numbers.astype('<i8').tobytes()).hexdigest();checked=evidence['validation']
        C.need(numbers.tolist()==task['source_atomic_numbers']==extra['atomic_numbers']
            and atom==old['atom_order_sha256']==extra['atom_order_sha256']==checked['atom_order_sha256']
            and C.value_sha(graph)==checked['ordered_graph_sha256']
            and signature==old['stereo_signature']==extra['stereo_signature']==checked['stereo_signature']
            and source==extra['stereo_source'] and old['source_record_id']==extra['source_record_id']==pointer['record_id']
            and io.geometry_sha(numbers,pm7_xyz)==checked['pm7_geometry_sha256']
            and io.geometry_sha(numbers,old['coordinates'])==checked['baseline_geometry_sha256'],
            'INDEPENDENT_ORIGINAL_GRAPH_ATOMS_STEREO_SOURCE_AND_F64_ANCHORS')
        C.need(ORIGINAL.stereo(mol,old['coordinates'],science) and ORIGINAL.stereo(mol,extra['coordinates'],science),
            'INDEPENDENT_BASELINE_AND_SUPPLEMENT_GEOMETRIC_STEREO')
        for event in packet['candidate_optimizer_events']:
            if event['finite']:
                C.need(ORIGINAL.stereo(mol,event['coordinates'],science)==event['stereo_valid'],'ORIGINAL_RETAINED_EVENT_STEREO_FLAG_READBACK')
        baseline=dict(candidate_key='existing:000000',candidate_id=None,coordinates=old['coordinates'],
            energy=float(old['uff_energy_kcal_mol']),seed=old['seed'],origin='accepted_sprime',
            geometry_sha256=packet['baseline_identity']['geometry_sha256'])
        distance=lambda left,right:science.rmsd(mol,left['coordinates'],right['coordinates'])
        chosen=C.select_real_second(entry['molecule_id'],baseline,packet['candidate_optimizer_events'],distance,CTX['selection'])
        second=chosen['second']
        C.need(second is not None and second['candidate_key']==extra['optimizer_event_key']
            and second['geometry_sha256']==extra['geometry_sha256'] and second['coordinates']==extra['coordinates']
            and second['below_dedup_threshold']==extra['below_dedup_threshold'],'UNCHANGED_ORIGINAL_0P5_REAL_SECOND_SELECTION')
        accepted=ID.integrate(task,packet,info,science,CTX['graph_source'],entry['packet_reference'],evidence)
        C.need(accepted is not None,'REAL_SOURCE_SUPPLEMENT_REQUIRED_FOR_PHYSICAL_VIEW')
        accepted['row'].update(native_uid=1278,native_endpoint='202.38.247.57:22',native_parent_job_id=job,
            native_packet_origin_reference=entry['packet_reference'],native_claim_origin_reference=entry['claim_reference'],
            prior_Main_source_not_Alpha_import=True,physical_QA_parent_job_id=CTX['parent']['job_id'],physical_QA_uid=1278)
        result.update(status='INDEPENDENT_MAIN_GRAPH_STEREO_AND_PHYSICAL_ID_VALIDATED',accepted=accepted,
            below_dedup_threshold=extra['below_dedup_threshold'],independently_observed_baseline_rmsd_A=distance(baseline,second),
            original_native_baseline_rmsd_A=extra['min_rmsd_to_previously_selected_A'])
    except Exception as error:result.update(error=repr(error),traceback=traceback.format_exc())
    return result