"""Read/adopt finite Root storage authority; never reserves quota or trains."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).absolute().parents[2]
sys.path.insert(0,str(REPO/'current'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('validate','census','inspect','allocate','register-root','seal','ack'))
    parser.add_argument('--request',type=Path,required=True); parser.add_argument('--request-sha256',required=True)
    parser.add_argument('--input',choices=('authoritative_proxy','synthetic'),default='authoritative_proxy')
    parser.add_argument('--engineering-only',action='store_true')
    parser.add_argument('--job-root',type=Path); parser.add_argument('--Root-closure',dest='closure',type=Path)
    parser.add_argument('--segment-id'); parser.add_argument('--root',type=Path)
    parser.add_argument('--root-kind',choices=('training','checkpoint','failed','SDK','cache','external_guard','H0_panel','source_snapshot','management'))
    parser.add_argument('--entry-type',choices=('directory','file'),default='directory')
    for name in ('event','result','evidence','lineage-root'): parser.add_argument('--'+name,type=Path)
    args = parser.parse_args()
    from phychem_mfm.phase1 import v3_proxy_run as proxy
    from phychem_mfm.phase1.v3_long_run_storage import validate_admission,DurableLedger,controller_class
    from phychem_mfm.phase1.v3_sample_budget_events import binding,read_bound
    ref = binding(args.request); proxy.require(ref['sha256'] == args.request_sha256,'Exact request raw SHA required')
    request = read_bound(ref); config = read_bound(request['configuration'])
    # This verifies original source/science admission as well; an operational
    # tool cannot promote a forged science profile by avoiding the normal gate.
    proxy.validate_request(request,input_kind=args.input,engineering_only=args.engineering_only)
    if args.command == 'validate':
        value = validate_admission(request,config)
        print(json.dumps({'status':'OPERATIONAL_EVIDENCE_VALID','scientific_acceptance':False,
            'reservation_created_by_this_tool':False,'quota':value['quota']})); return
    ledger = DurableLedger(request,config)
    if args.command == 'allocate':
        proxy.require(args.segment_id and args.job_root is not None and args.lineage_root is not None,'Allocation needs exact admitted segment/job/canonical roots')
        print(json.dumps(ledger.allocate_segment(request_ref=ref,segment_id=args.segment_id,job_root=args.job_root,lineage_root=args.lineage_root))); return
    if args.command == 'register-root':
        proxy.require(args.root is not None and args.root_kind is not None,'Explicit declared root and kind required')
        entries = read_bound(request['long_run']['Root_segment_admission'])['external_roots']
        matches = [entry for entry in entries if Path(entry['path']).absolute() == args.root.absolute()
            and entry['kind'] == args.root_kind and entry['type'] == args.entry_type]
        proxy.require(len(matches) == 1,'Root is not uniquely listed in current Root operational admission')
        print(json.dumps(ledger.register_root(args.root,kind=args.root_kind,entry_type=args.entry_type,must_exist=matches[0]['must_exist']))); return
    if args.command == 'census': print(json.dumps(ledger.refresh())); return
    if args.command == 'inspect':
        print(json.dumps({'actual':ledger.refresh(),'records':ledger.records(),'roots':ledger.root_records(),
            'reservation_created_by_this_tool':False})); return
    if args.command == 'seal':
        proxy.require(args.job_root is not None and args.closure is not None,'Seal needs exact job root and actual Root closure')
        print(json.dumps(ledger.seal_segment(job_root=args.job_root,Root_closure_ref=binding(args.closure)))); return
    proxy.require(all(getattr(args,key) is not None for key in ('event','result','evidence','lineage_root')),'ACK needs existing actual panel/evidence and canonical ledger')
    contract = read_bound(binding(args.lineage_root/'EXPERIMENT.json'))['contract']
    controller = controller_class()(args.lineage_root,contract=contract,max_records=contract['plan']['max_total_checkpoints'],
        maximum_bytes=config['proxy_contract']['resources']['ledger_bytes'])
    controller.storage = ledger
    print(json.dumps(controller.acknowledge(*(binding(getattr(args,key)) for key in ('event','result','evidence')))))


if __name__ == '__main__': main()
