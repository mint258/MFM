"""Resource/authority wrapper. The entire frozen full science main is direct."""
import argparse,datetime,os,threading,time
from pathlib import Path
from . import contract as C,io as I
from .book import Book
from workflows.data_v1_final.labels.full_projection_v1 import run as F
from workflows.data_v1_final.labels.bounded_projection_v1 import run as B
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as R


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','startup-proof','output'):p.add_argument('--'+k,required=True)
    a=p.parse_args();cfg=I.load(a.config);review=I.load(I.require(cfg['full_review_reference']));C.budget(review)
    C.need(cfg['recovery_schema']==C.SUMMARY and cfg['recovery_resource_review_reference']==cfg['full_review_reference'],'ONLY_THIS_RECOVERY_BOOK_CONFIG')
    proof=I.admit(a.startup_proof,a.config,C.RUN_KEY,cfg['scope_parameters'],cfg['whole_output_cap_bytes'],cfg['recovery_wall_seconds'],cfg['small_references'])
    I.actual(cfg['seed_actual_references'],'workflows.data_v1_final.labels.full_recovery_book_v1.seed')
    out=Path(a.output).absolute();control=Path(str(out)+'_recovery_control');C.need(not out.exists() and not control.exists(),'NEW_BATCH_AND_TECHNICAL_OUTPUT')
    control.mkdir(parents=True,mode=0o700);gate=I.fixtures(control/'fixtures.json')
    summary=I.load(I.require(cfg['adoption_summary_reference']))
    C.need(summary['schema']==C.SUMMARY and summary['resource_review_reference']==cfg['full_review_reference']
      and summary['new_book_path']==cfg['dispatch_book_path'],'EXACT_SEEDED_NEW_BOOK_AND_ROOT_REVIEW')
    book=Book(cfg['dispatch_book_path'])
    try:
        snapshot=book.snapshot();selectors=I.load(I.require(cfg['selector_reference']))['sources']
        C.need(snapshot['adoption_summary_reference']==cfg['adoption_summary_reference'],'SAME_IMPORTED_ORIGIN')
        book.assert_claim(cfg['batch_name'],I.pin(a.config),selectors)
        future=C.remaining(snapshot['metadata'],snapshot['batches'])
    finally:book.close()
    C.need(proof['account_free_bytes']>=200000000000+future+(2<<30)+review['other_storage_scope_unwritten_cap_upper_bound_bytes'],
      'FRESH_NEW_PRODUCTION_REMAINING_PLUS_CLOSURE_AND_OTHER_CAPS_NO_DOUBLE_OLD_QUOTA')
    C.need(F.worker is B.worker and F.initialize is B.initialize,'DIRECT_FROZEN_SCIENCE_WORKER_OBJECTS')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.slurm_format import fields
    start=datetime.datetime.fromisoformat(fields(proof['job_metadata'])['StartTime']).timestamp()
    cutoff=start+cfg['recovery_wall_seconds']-review['softwall_margin_seconds'];done=threading.Event();stopped=[]
    def softwall():
        while not done.wait(.5):
            if time.time()>=cutoff and R.control() is not None:
                observation={'job_id':str(proof['job_id']),'cutoff_unix_seconds':cutoff,'observed_unix_seconds':time.time(),
                  'margin_seconds':review['softwall_margin_seconds'],'signals_sent':False}
                R.mark_stop('ROOT_REVIEWED_SOFTWALL_STOP_NEW_WINDOWS_NATURAL_DRAIN',observation);stopped.append(observation);return
    t=threading.Thread(target=softwall,name='labels-softwall-no-signals',daemon=True);t.start();ok=False
    try:
        F.main();ok=True  # No old global variable or function is replaced.
    finally:
        done.set();t.join(timeout=2)
        from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import unique_bytes
        charged=(unique_bytes(out) if out.exists() else 0)+sum(p.stat().st_size for p in control.iterdir() if p.is_file())+(64<<20)+(2<<20)
        C.need(charged<=cfg['whole_output_cap_bytes'],'WHOLE_BATCH_AND_WRAPPER_CAP_WITHOUT_OLD_CACHE_COPY')
        ref=I.write_new(control/'receipt.json',{'schema':'LABELS_RECOVERED_DIRECT_RUN_WRAPPER_V1',
          'status':'ORIGINAL_FULL_MAIN_RETURNED_PARENT_C0_STILL_REQUIRES_ACCOUNTING' if ok else 'ORIGINAL_MAIN_FAILED_PARTIALS_RETAINED',
          'job_id':str(proof['job_id']),'config_reference':I.pin(a.config),'fixture_gate':gate,
          'direct_original_main_and_workers':True,'charged_output_bytes_including_wrapper_reserves':charged,'original_worker_parse_masks_modified':False,
          'adoption_summary_reference':cfg['adoption_summary_reference'],'softwall_observations':stopped,
          'old_parent_state':'TIMEOUT','old_book_written':False,'signals_sent':False,'automatic_retry':False})
        C.need(sum(p.stat().st_size for p in control.iterdir() if p.is_file())<=1<<20,'WRAPPER_WITHIN_ORIGINAL2MIB_MANIFEST_RESERVE')

if __name__=='__main__':main()