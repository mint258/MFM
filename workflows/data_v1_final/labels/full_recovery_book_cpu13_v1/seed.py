"""CPU-only adoption after real complete inventory C0 and explicit Root selection."""
from __future__ import annotations
import argparse,collections,json,re,time
from pathlib import Path
from workflows.data_v1_final.labels.full_recovery_book_v1 import contract as C
from . import binding as I
from workflows.data_v1_final.labels.full_recovery_book_v1.book import Book
from .coverage import write_adopted_sidecar,source_inverse
from workflows.data_v1_final.labels.full_timeout_inventory_v1 import inventory as V
from workflows.data_v1_final.labels.full_timeout_inventory_v1.contract import cursor_chain


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('plan','startup-proof','output'):p.add_argument('--'+k,required=True)
    a=p.parse_args();plan=I.load(a.plan);C.need(plan['schema']==C.SEED,'SEED_SCHEMA')
    review=I.load(I.require(plan['resource_review_reference']));values=C.budget(review)
    C.need(review['inventory_resource_adoption_reference']==plan['inventory_resource_adoption_reference'],'EXACT_CPU13_RESOURCE_ADOPTION_REVIEW')
    selection=I.load(I.require(plan['selection_reference']));inv=I.load(I.require(plan['inventory_actual_references']['receipt']))
    I.inventory_gate(inv,plan['inventory_actual_references'],plan['inventory_resource_adoption_reference']);I.actual(plan['inventory_actual_references'],I.INVENTORY_MODULE)
    C.need(selection['schema']==C.SELECTION and selection['status']=='ROOT_APPROVED' and selection['reviewer']=='root' and selection['reason'].strip()
      and selection['inventory_receipt_reference']==plan['inventory_actual_references']['receipt']==review['inventory_receipt_reference']
      and review['seed_selection_reference']==plan['selection_reference'],'ACTUAL_ROOT_EXPLICIT_SEED_SELECTION_AND_NEW_RESOURCE_REVIEW')
    proof=I.admit(a.startup_proof,a.plan,C.SEED_KEY,plan['scope_parameters'],values['seed'],review['seed_wall_seconds'],plan['small_references'])
    root=I.new_root(a.output);C.need(str(root)==plan['output'],'EXACT_NEW_SEED_OUTPUT')
    try:
        gate=I.fixtures(root/'recovery_fixtures.json');inverse=source_inverse()
        deadline=I.start(proof,root,plan['resource_review_reference'],values['seed']+values['production']+(2<<30),review['seed_wall_seconds'])
        # Only now old output DATA is read. No old DB is opened writable.
        original=I.load(I.require(plan['original_inventory_plan_reference']))
        cfg=I.load(I.require(original['original_references']['config']));master=I.load(I.require(cfg['master_reference']))
        C.need(proof['request'].get('data_references',[])==[inv['evidence_reference'],*original['known_data_references']]
          and proof['request'].get('deferred_authority_references',[])==[original['closed_locator_inventory_reference']],
          'EXACT_REGISTERED_OLD_OUTPUT_DATA_AND_TRANSITIVE_LOCATOR_AUTHORITY')
        C.need(review['master_reference']==cfg['master_reference'],'UNCHANGED_SOURCE_MASTER')
        locators=I.load(I.require(original['closed_locator_inventory_reference']))
        books=V.audit_books(original,cfg,locators,deadline)
        evidence=inv['evidence_reference'];iref=plan['inventory_actual_references']['receipt']
        iroot=Path(iref['path']).parent
        C.need(Path(evidence['path'])==iroot/'evidence.jsonl' and evidence['bytes']<=128<<20,'ACTUAL_INVENTORY_EVIDENCE_ONLY')
        I.data_ref(evidence['path'],deadline,evidence);verified={};records=[];db_seen=0
        with I.reader(evidence['path'],I.frame(Path(evidence['path']).lstat()),deadline) as (f,_):
            while True:
                line=f.readline((2<<20)+1)
                if not line:break
                C.need(len(line)<=2<<20,'BOUNDED_INVENTORY_RECORD');r=json.loads(line);records.append(r)
                if r['kind']=='old_readonly_database_observations':
                    C.need(r['book']['reference']==books['book']['reference'] and r['state']['reference']==books['state']['reference']
                      and r['actual_range_plan']['reference']==books['actual_range_plan']['reference'],'CURRENT_OLD_SHA_EQUALS_REAL_INVENTORY_SNAPSHOT');db_seen+=1
                if r['kind']=='committed_window':
                    k=(r['window']['range_id'],r['window']['lo']);C.need(k not in verified and r['status']=='VERIFIED_COMMITTED_WINDOW','ALL_WINDOW_RESULTS_COMPLETE_UNIQUE')
                    verified[k]=r
        C.need(db_seen==1 and len(verified)==len(books['windows'])==inv['old_committed_windows']==inv['cpu_verified_committed_windows'],
          'COMPLETE_WINDOW_SET_NOT_COUNT_ONLY_PASS')
        for w in books['windows']:C.need(verified[w['range_id'],w['lo']]['window']==w,'EXACT_COMMITTED_WINDOW_RECEIPT_SET')
        cursor_chain(books['ranges'],books['tickets'],books['windows'],books['expected'])
        assigned={e['file_id'] for e in books['expected']};range_file={e['range_id']:e['file_id'] for e in books['expected']}
        ticket_file={t['ticket']:range_file[t['range_id']] for t in books['tickets']};orphans=set()
        for r in records:
            if 'original_worker_checkpoint' in r:
                for err in r['original_worker_checkpoint']['errors']:
                    fid=range_file.get(err.get('range_id'));orphans.update(assigned if fid is None else {fid})
            if r['kind']!='uncommitted_or_auxiliary_file':continue
            C.need(r['status']=='HASHED_RETAINED_NEVER_SCIENTIFICALLY_ACCEPTED','UNVERIFIED_AUX_OR_ORPHAN_STILL_HOLD')
            name=r['relative']
            if re.fullmatch(r'worker_[0-9]{2}[.]json',name) or name in ('full_organization_fixture_gate.json','failure.json','manifest.json'):continue
            match=re.search(r'(?:part_|window_)([0-9a-f]{32})',name)
            fid=ticket_file.get(match[1]) if match else None
            orphans.update(assigned if fid is None else {fid})
        chosen,cursors,holds,consumed=C.prefixes(books['expected'],books['ranges'],books['tickets'],books['windows'],verified,
          selection['selected_prefixes'],orphans)
        authorized={p['reference']['path']:p['reference'] for r in chosen for p in r['parts']}
        membership=I.write_new(root/'adoption_membership.json',{'schema':'LABELS_ADOPTED_AND_CONSUMED_MEMBERSHIP_V1',
          'selected_verified_windows':chosen,'all_old_consumed_windows':consumed,'all_old_tickets':books['tickets'],
          'holds':holds,'original_inventory_evidence_reference':evidence,'old_parent_state':'TIMEOUT'},cap=64<<20)
        sidecfg=dict(cfg);sidecfg['sidecar_reserve_bytes']=2<<30
        snap={'closed_windows':[r['window'] for r in chosen]}
        sidecar=write_adopted_sidecar(root,sidecfg,snap,authorized,deadline)
        stats=collections.defaultdict(collections.Counter)
        for k,v in sidecar['field_stats_by_source_role'].items():stats[str(json.loads(k)[1])].update(v)
        C.need(not C.hold_fields(stats),'ORIGINAL1PCT_ADOPTED_PREFIX_QUALITY_HOLD_NO_NEW_BOOK')
        # Repeat old DB hash before committing any new recovery authority.
        for key in ('book','state'):I.data_ref(books[key]['reference']['path'],deadline,books[key]['reference'])
        listing=I.OLD.locator_inventory(C.OLD,C.OLDBOOK)
        C.need(set(listing['files'])==set(locators['files']) and set(listing['directories'])==set(locators['directories']),
          'NO_UNDECLARED_OLD_ARTIFACT_DISAPPEARANCE_OR_ADDITION')
        for group in ('files','directories'):
            for name,current in listing[group].items():
                previous=locators[group][name]
                C.need(all(current[k]==previous[k] for k in ('inode','bytes','mtime_ns','ctime_ns','uid','mode','nlink')),
                  'ALL_OLD_PORTABLE_FRAMES_RECHECKED_BEFORE_NEW_BOOK')
        summary={'schema':C.SUMMARY,'origin':C.ORIGIN,'status':'ADOPTED_PREFIX_AND_HOLDS_RECORDED_NOT_OLD_C0',
          'old_parent_state':'TIMEOUT','old_parent_c0':False,'old_allocated_core_seconds':230592,'job_id':str(proof['job_id']),
          'plan_reference':I.pin(a.plan),'inventory_actual_references':plan['inventory_actual_references'],
          'old_parent_actual_references':original['original_references'],
          'inventory_resource_adoption_reference':plan['inventory_resource_adoption_reference'],
          'seed_selection_reference':plan['selection_reference'],'resource_review_reference':plan['resource_review_reference'],
          'master_reference':cfg['master_reference'],'original_config_reference':original['original_references']['config'],
          'canonical_index':cfg['canonical_index'],'adoption_membership_reference':membership,'sidecar':sidecar,
          'closed_physical_intervals':[{'file_id':range_file[r['window']['range_id']],'lo':r['window']['lo'],'hi':r['window']['hi']} for r in chosen],
          'source_initial_cursors':cursors,'source_holds':holds,'new_book_path':str(root/'recovered_book.sqlite'),
          'storage_basis':values,'quality_hold_fields':[],'original_book_and_leases_written':False,
          'final_common_D4':False,'candidate_masks_frozen':False,'normalization_completed':False,'new_UFF_QM_calls':0,
          'fixture_gate':gate,'source_inverse_proof':inverse,'all_old_unknown_consumed_retained':True}
        sr=I.write_new(root/'adoption_summary.json',summary)
        book=Book(root/'recovered_book.sqlite',True,files=master['sources'],review=review,master_ref=cfg['master_reference'],
          review_ref=plan['resource_review_reference'],summary_ref=sr,selected_cursors=cursors,holds=holds)
        book.close();br,_=I.data_ref(root/'recovered_book.sqlite',deadline)
        receipt={'schema':'LABELS_RECOVERED_BOOK_SEED_RECEIPT_V1','status':'NEW_BOOK_CREATED_ROOT_CONTINUATION_REVIEW_REQUIRED',
          'job_id':str(proof['job_id']),'plan_reference':I.pin(a.plan),'startup_request_reference':proof['request_reference'],
          'summary_reference':sr,'initial_new_book_reference':br,'old_parent_state':'TIMEOUT','old_parent_c0':False,
          'old_book_written':False,'new_UFF_QM_calls':0,'future_scientific_parent_C0_not_claimed':True,'fixture_gate':gate}
        I.write_new(root/'receipt.json',receipt)
        C.need(sum(p.stat().st_size for p in root.rglob('*') if p.is_file())+(64<<20)<=values['seed'],'SEED_TOTAL_OUTPUT_WITH_OBSERVER_RESERVE')
        print(json.dumps({'status':receipt['status'],'adopted_windows':len(chosen),'held_sources':len(holds)}),flush=True)
    except BaseException as exc:
        I.write_new(root/'failure.json',{'error':type(exc).__name__+':'+str(exc)[:500],'new_book_may_exist_do_not_retry':True,
          'old_book_written':False,'automatic_retry':False,'old_parent_state':'TIMEOUT'});raise

if __name__=='__main__':main()