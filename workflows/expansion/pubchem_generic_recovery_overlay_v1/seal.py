"""Root metadata-only completion sealing after actual overlay C0/review exists."""
import argparse
import os
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from .runtime import VERSION,read,actual_parent


def seal(producer_ref,review_ref):
    Q.need(os.getuid()==1264,'Actual Alpha metadata sealing, no Main identity transplant')
    producer=read(producer_ref);review=read(review_ref)
    Q.need(producer['schema']=='PUBCHEM_EXACT_MINCID_OVERLAY_PRODUCER_V1'
        and producer['status']=='OVERLAY_CLOSED_PENDING_ROOT_ACTUAL_C0' and producer['population_version']==VERSION
        and review['schema']=='ROOT_PUBCHEM_GENERIC_RECOVERY_OVERLAY_ACTUAL_REVIEW_V1'
        and review['status']=='APPROVED_UNFILTERED_POPULATION_OVERLAY' and review['reviewer']=='root'
        and review['producer_receipt_reference']==producer_ref and review['scientific_population_recovery_accepted'] is True,
        'Actual existing overlay source acceptance only; no approval synthesized by seal')
    p=actual_parent(review);Q.need(str(p['JobIDRaw'])==producer['profile_admission']['job_id'],'Actual source parent matches')
    r=producer['result'];pool={k:v for k,v in r.items() if k not in ('schema','proposed_effective_source_counts','scientific_population_recovery_accepted')}
    pool.update(schema='PUBCHEM_EXACT_MINCID_OVERLAY_POOL_V1',status='MATERIALIZED_UNFILTERED_NO_RELEASE',
        source_endpoint='218.192.171.238:22',source_uid=1264,producer_receipt_reference=producer_ref,root_actual_review_reference=review_ref,
        source_counts=r['proposed_effective_source_counts'],aliases_rows=r['counts']['aliases_rows'],unique_full_keys=r['counts']['unique_full_keys'],
        scientific_population_recovery_accepted=True)
    from .reader import validate_header
    validate_header(pool)
    return pool


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--producer',required=True,type=Path)
    p.add_argument('--actual-review',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    Q.need(str(a.output.absolute()).startswith('/gfshome/alpha/'),'Only real Alpha metadata destination')
    value=seal(Q.reference(a.producer),Q.reference(a.actual_review));Q.write(a.output,value)


if __name__=='__main__':main()
