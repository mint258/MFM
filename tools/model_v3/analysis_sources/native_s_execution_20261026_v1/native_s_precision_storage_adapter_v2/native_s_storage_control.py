"""Root read-only admission and bounded accounting controls; never reserves."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import native_s_storage as native


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('validate','census','inspect','allocate','seal'))
    parser.add_argument('--request',type=Path,required=True)
    parser.add_argument('--request-sha256',required=True)
    parser.add_argument('--job-root',type=Path)
    parser.add_argument('--lineage-root',type=Path)
    parser.add_argument('--segment-id')
    parser.add_argument('--Root-closure',dest='closure',type=Path)
    args=parser.parse_args()
    preliminary=json.loads(args.request.read_text()); config0=__import__('runtime_origin').read_qa_reference(preliminary['configuration'])
    storage,pins=native.load_runtime(allow_candidate_profile=config0['purpose']==native.PROFILE)
    ref=storage.binding(args.request)
    native.require(ref['sha256']==args.request_sha256,'Exact native request bytes required')
    request=storage.read_bound(ref); config=storage.read_bound(request['configuration'])
    native.check_runtime_binding(request,config,pins)
    native.require(config['Root_runtime_pin']==native.runtime_pin(pins),'Exact combined runtime source pin differs')
    checked=native.validate_admission(request,config,storage)
    if args.command=='validate':
        print(json.dumps(dict(status='NATIVE_OPERATIONAL_EVIDENCE_VALID',
            purpose=config['purpose'],quota=checked['quota'],
            reservation_created_by_this_tool=False,scientific_acceptance=False)))
        return
    ledger=native.ledger_class(storage)(request,config)
    if args.command=='census': result=ledger.refresh()
    elif args.command=='inspect': result=dict(actual=ledger.refresh(),records=ledger.records(),roots=ledger.root_records())
    elif args.command=='allocate':
        native.require(args.segment_id and args.job_root is not None and args.lineage_root is not None,
            'Exact allocated segment/job/lineage roots required')
        result=ledger.allocate_segment(request_ref=ref,segment_id=args.segment_id,
            job_root=args.job_root,lineage_root=args.lineage_root)
    else:
        native.require(args.job_root is not None and args.closure is not None,'Exact actual Root terminal closure required')
        result=ledger.seal_segment(job_root=args.job_root,Root_closure_ref=storage.binding(args.closure))
    print(json.dumps(dict(result=result,reservation_created_by_this_tool=False,
        D5_authority=False,scientific_acceptance=False)))


if __name__=='__main__': main()
