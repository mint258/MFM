"""Reuse real closed Gluster inode witnesses without a cross-node device claim."""
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from ..pubchem_alpha_technical_unknown_audit_v1.scan import frame
from .runtime import read


def historical(ref,ledger):
    Q.need(ledger['schema']=='ROOT_OTHER_FUTURE_CLOSED_SCOPE_CREDIT_V1' and ledger['endpoint']=='218.192.171.238:22'
        and ledger['uid']==1264 and '1885149' in ledger['source_C0_jobs'],'Actual Alpha closed source ledger')
    matches=[x for x in ledger['closed_immutable_retained_files'] if x['reference']==ref]
    Q.need(len(matches)==1,'Exact historical body reference, never basename matching')
    old=matches[0];current=frame(Path(ref['path']).lstat())
    Q.need(current['st_size']==ref['bytes'] and current['st_ino']==old['inode']
        and current['st_mtime_ns']==old['mtime_ns'] and current['st_ctime_ns']==old['ctime_ns'],
        'Actual original closed inode/bytes/mtime/ctime unchanged')
    return dict(reference=ref,current_frame=current,historical_frame=old,fresh_full_body_SHA_verified=False,
        historical_full_SHA_and_actual_C0_reused=True,device_identity_cross_node_claimed=False,
        device_note='Gluster st_dev is client-local. Historical ledger has no host/volume fields. Current native Guard independently binds live quota root/volume/endpoint; full current before/after frame includes device.')


def unchanged(witness):
    Q.need(frame(Path(witness['reference']['path']).lstat())==witness['current_frame'],'Full current same-node frame stable including device')
