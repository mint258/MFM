"""Small closed-source metadata collector; does not load geometry or D27 arrays.

Retain all original source/role pins and add only four required JSON replicas.
Never attach the full11,488-body calibration transport to a UFF Capsule: Capsule
validates each member, and that would introduce unnecessary10GB DATA reads.
"""
import argparse
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from .quality_authority import accepted,read,completed


def triple(ref):return {k:ref[k]for k in ('path','bytes','sha256')}

def key(ref):return Q.canonical(triple(ref))


def closed_transport(ref):
    t=read(ref)
    Q.need(t['schema']=='PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1'
        and t['status']=='VERIFIED_REPLICAS_CLOSED'
        and t['destination']=={'endpoint':Q.ENDPOINT,'uid':Q.UID},'Actual closed Alpha transport required')
    return t


def select_replicas(original,extra,needed):
    """Pure metadata projection; duplicate origins must preserve original bytes."""
    entries={key(item['source_reference']):item for item in original['replicas']}
    Q.need(len(entries)==len(original['replicas']),'Duplicate original capsule origin')
    more={key(item['source_reference']):item for item in extra['replicas']}
    Q.need(len(more)==len(extra['replicas']),'Duplicate extra transport origin')
    for ref in needed:
        k=key(ref);Q.need(k in entries or k in more,'Missing required original JSON transport pin')
        if k not in entries:entries[k]=more[k]
        item=entries[k]
        Q.need(item['source_reference']['bytes']==item['replica_reference']['bytes']
            and item['source_reference']['sha256']==item['replica_reference']['sha256']
            and item['origin_endpoint']and type(item['origin_uid'])is int,'Exact original source identity retained')
    return list(entries.values())


def collect(capsule_ref,quality_ref,extra_ref,transport_review_ref,output):
    review,cal,domain=accepted(quality_ref)
    capsule=read(capsule_ref);base=closed_transport(capsule['source_transport_manifest'])
    extra=closed_transport(extra_ref);transport_review=read(transport_review_ref)
    Q.need(capsule['schema']=='PUBCHEM_ORIGINAL_UFF_SOURCE_CAPSULE_V1'
        and capsule['status']=='ACTUAL_CLOSED_SOURCE_CAPSULE'
        and capsule['destination']=={'endpoint':Q.ENDPOINT,'uid':Q.UID},'Actual original UFF source capsule')
    Q.need(transport_review['schema']=='ROOT_PUBCHEM_D27_ALPHA_TRANSPORT_ACTUAL_ACCEPTANCE_V1'
        and transport_review['status']=='APPROVED_EXACT_D27_INPUT_REPLICAS'
        and transport_review['reviewer']=='root'and transport_review['transport_manifest_reference']==extra_ref,
        'Independent actual closed D27 replica authority required')
    completed(transport_review)
    replica_index={key(i['source_reference']):i['replica_reference']for i in extra['replicas']}
    cfg=Q.load(Q.verify(replica_index[key(review['original_mask_config_reference'])]))
    needed=[review['field_map_reference'],review['original_mask_config_reference'],
            cfg['sources']['mask_rules'],cfg['sources']['registry']]
    replicas=select_replicas(base,extra,needed)
    index={key(i['source_reference']):i['replica_reference']for i in replicas}
    for ref in needed:
        Q.verify(index[key(ref)])
        adopted=review.get('actual_field_map_and_mask_replicas',{}).get(
            next((name for name in ('field_map_reference','original_mask_config_reference')if review[name]==ref),''))
        if adopted:Q.need(index[key(ref)]==adopted,'Same independently reviewed189 actual JSON replica')
    # Original source pins already resolve to named code files in the capsule.
    # Do not substitute anonymous calibration blob files for Python modules.
    for pin in cfg['adapter_source_pins']:
        Q.need(key(pin)in index and Path(index[key(pin)]['path']).suffix=='.py',
               'Every original mask adapter must retain named actual Python source')
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    merged={**base,'replicas':replicas,'original_UFF_transport_reference':capsule['source_transport_manifest'],
            'added_D27_metadata_transport_reference':extra_ref,'D27_transport_actual_review_reference':transport_review_ref}
    transport_pin=Q.write(root/'source_and_quality_transport.json',merged)
    derived={**capsule,'source_transport_manifest':transport_pin,'original_source_capsule_reference':capsule_ref,
             'full_Common_TRAIN_quality_actual_review_reference':quality_ref,
             'source_roles_and_original_science_pins_unchanged':True}
    capsule_pin=Q.write(root/'source_and_quality_capsule.json',derived)
    return Q.write(root/'bindings.json',dict(schema='PUBCHEM_ALPHA_UFF_FULLTRAIN_QUALITY_BINDINGS_V1',
        status='SOURCE_METADATA_BOUND_NOT_NATIVE_UFF_OR_PRODUCTION_ACCEPTANCE',
        source_capsule_reference=capsule_pin,parent_transport_manifest=transport_pin,
        quality_reference_review=quality_ref,original_source_capsule_reference=capsule_ref,
        quality_transport_actual_review_reference=transport_review_ref,
        original_scientific_functions_recomputed=False,new_geometry_or_QM_calls=0))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source-capsule','quality-review','quality-transport','transport-actual-review','output'):
        p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();collect(Q.reference(a.source_capsule),Q.reference(a.quality_review),
        Q.reference(a.quality_transport),Q.reference(a.transport_actual_review),a.output)


if __name__=='__main__':main()