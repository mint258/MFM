"""Verify all10 input replicas only; no source manifest adoption or index creation."""
import argparse
import io
import json
from pathlib import Path
import traceback
import unittest
from .reader import ReplicaVerifier,MAIN,ALPHA,triple,key,S
from .runtime import admit

DATASETS={'v1_all_roles_and_embargo','expansionrx','som_cyp','som_az','qm7','qm9','tdc_admet',
          'moleculenet','marcel_drugs75k','marcel_kraken'}


def bindings(plan):
    inventory=S.load(plan['inventory_reference']);delta=S.load(plan['authority_delta_reference'])
    S.need(inventory['schema']=='PUBCHEM_NONCOCONUT_ALPHA_TRANSFER_INVENTORY_V1'
           and inventory['status']=='INVENTORIED_NOT_TRANSFERRED_NOT_ADOPTED'
           and inventory['origin']==dict(endpoint=MAIN,uid=1278)
           and inventory['destination']==dict(endpoint=ALPHA,uid=1264)
           and {s['dataset'] for s in inventory['sources']}==DATASETS and len(inventory['sources'])==10,
           'ACTUAL_EXACT_ALL10_INVENTORY_NOT_ALL11_OR_COCO_SCOPE')
    original=delta['base_inventory_reference']
    S.need(delta['schema']=='PUBCHEM_NONCOCONUT_AUTHORITY_TRANSFER_DELTA_V1'
           and all(original[k]==plan['inventory_reference'][k] for k in ('bytes','sha256')),
           'EXACT_UNCHANGED_BASE_INVENTORY_BYTES_BEHIND_AUTHORITY_DELTA')
    root=Path(plan['replica_root'])
    S.need(root.is_absolute() and root.is_relative_to('/gfshome/alpha') and '..' not in root.parts
           and plan['replica_layout']=='SHA256_OBJECT_PLUS_ORIGINAL_FILENAME_V1','EXPLICIT_REVIEWED_CONTENT_ADDRESSED_REPLICA_LAYOUT')
    chosen={key(item['source_reference']):triple(item['replica_reference']) for item in plan.get('replica_bindings',[])}
    result=[];seen=set()
    for entry in [*inventory['entries'],*delta['entries']]:
        source=triple(entry['source_reference']);identity=key(source)
        S.need(identity not in seen and entry['origin_endpoint']==MAIN and entry['origin_uid']==1278,'ONE_EXACT_MAIN_ORIGIN_ENTRY_PER_SOURCE')
        seen.add(identity)
        possible=entry.get('existing_Alpha_declared_exact_byte_candidates',entry.get('existing_Alpha_exact_candidates',[]))
        if identity in chosen:replica=chosen[identity]
        elif possible:
            S.need(len(possible)==1,'AMBIGUOUS_EXISTING_REPLICA_REQUIRES_EXPLICIT_ROOT_BINDING')
            replica=triple(possible[0].get('reference',possible[0].get('replica_reference')))
        else:
            path=root/'objects'/source['sha256']/Path(source['path']).name
            replica=dict(source,path=str(path))
            if entry.get('proposed_replica_reference'):S.need(replica==entry['proposed_replica_reference'],'ROOT_LAYOUT_AND_ORIGINAL_PROPOSED_EXACT_PATH_MATCH')
        result.append(dict(origin_endpoint=MAIN,origin_uid=1278,source_reference=source,replica_reference=replica))
    S.need(set(chosen)<=seen,'ROOT_BINDING_OUTSIDE_EXACT_INVENTORY_SCOPE')
    return inventory,result


def execute(plan,out,guard):
    inventory,selected=bindings(plan);reader=ReplicaVerifier(plan,selected,guard.check)
    for i,item in enumerate(selected,1):
        reader.verify(item['source_reference']);guard.check()
        if i%25==0:print(json.dumps(dict(event='SOURCE_REPLICA_VERIFIED',files=i,total=len(selected))),flush=True)
    S.need(len(reader.consumption)==len(selected),'EVERY_SELECTED_SOURCE_BODY_WHOLE_SHA_VERIFIED')
    for item in selected:
        path,_=reader.resolve(item['source_reference'])
        S.need(S.frame(path.stat())==reader.verified[key(item['source_reference'])],
               'VERIFIED_INPUT_FRAME_CHANGED_BEFORE_TRANSPORT_CLOSURE '+str(path))
    guard.check()
    manifest=dict(schema='PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1',status='VERIFIED_REPLICAS_CLOSED',
        destination=dict(endpoint=ALPHA,uid=1264),replicas=selected,
        producer_inventory_reference=plan['inventory_reference'],authority_delta_reference=plan['authority_delta_reference'],
        original_Main_proofs_and_references_preserved=True,source_replica_only=True,
        all10_input_byte_replicas_closed=True,scientific_source_adoption=False,all11_ready=False,
        coconut_scope_changed=False,index_or_filter_created=False)
    manifest_ref=S.save(out/'parent_transport_manifest.json',manifest)
    proof_ref=S.save(out/'whole_source_replica_verification.json',dict(files=reader.consumption,
        current_native_whole_SHA_bytes=sum(item['source_reference']['bytes'] for item in selected),
        logical_reference_count=len(selected),datasets=sorted(DATASETS),no_future_COCONUT_manifest_read=True))
    return dict(schema='ALPHA_ALL10_SOURCE_REPLICA_CLOSURE_V1',status='SOURCE_REPLICAS_CLOSED_NO_SCIENTIFIC_ADOPTION',
        parent_transport_manifest=manifest_ref,whole_verification_reference=proof_ref,
        logical_references=len(selected),source_bytes=sum(i['source_reference']['bytes'] for i in selected),
        datasets=sorted(DATASETS),all10_source_scientific_statuses_changed=False,all11_ready=False,
        coconut_scope_changed=False,scope_approval_inferred=False,index_or_candidate_filter_created=False,
        future_all11_manifest_read=False,original_source_manifest_modified=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan=json.loads(args.plan.read_text());proof=json.loads(args.startup_proof.read_text())
    authority=admit(plan,proof,args.plan,args.startup_proof,'ALPHA_ALL10_SOURCE_REPLICA_PLAN_V1','alpha_all10_source_replica_v1')
    from workflows.expansion.alpha_runtime_v1.guard import Guard
    guard=Guard(plan);out=Path(plan['output_directory'])
    try:
        out.mkdir(parents=True,exist_ok=False)
        from .test_reader import Native
        Native.root=out
        stream=io.StringIO();tested=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Native))
        fixture=S.save(out/'source_tests.json',dict(tests=tested.testsRun,errors=len(tested.errors),failures=len(tested.failures),
            skips=len(tested.skipped),transcript=stream.getvalue()))
        S.need(tested.wasSuccessful() and tested.testsRun==2 and not tested.skipped,'TWO_NATIVE_EXPLICIT_ORIGIN_AND_TAMPER_SYMLINK_FIXTURES')
        result=execute(plan,out,guard)
        S.save(out/'receipt.json',dict(schema='ALPHA_ALL10_SOURCE_REPLICA_PRODUCER_V1',plan=S.pin(args.plan),
            startup_proof=S.pin(args.startup_proof),profile_admission=authority,source_tests=fixture,
            result=result,runtime=guard.receipt(),actual_parent_C0_pending_root_readback=True,
            scientific_adoption=False,all11_ready=False,coconut_scope_changed=False))
    except BaseException as exc:
        if out.is_dir():S.save(out/'failure.json',dict(error=repr(exc),traceback=traceback.format_exc(),
            partials_retained=True,all11_ready=False,source_scope_changed=False))
        raise
    finally:guard.close()


if __name__=='__main__':main()
