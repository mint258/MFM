"""Fresh CPP namespace or explicitly Root-approved closed same-namespace resume."""
import fcntl
import hashlib
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from . import authority

NAME='compiled_cache_namespace.json'


def binding(plan,adoption,query):
    return dict(schema='ALPHA_CPP_EXACT_QUERY_CACHE_NAMESPACE_V1',
        backend_adoption_reference=plan['backend_adoption_reference'],build_manifest_reference=adoption['build_manifest_reference'],
        binary_reference=adoption['binary_reference'],reference_manifest=plan['reference_manifest'],query_manifest=plan['query_manifest'],
        population_version=query.get('population_version'),filtered_pool_receipt=query['filtered_pool_receipt'],
        original_source_bindings=adoption['source_bindings'],prototype_sources=adoption['validated_source_references'],
        production_sources=[Q.reference(p)for p in sorted(Path(__file__).parent.glob('*.py'))])


def key(value):return 'cpp206-'+hashlib.sha256(Q.canonical(value)).hexdigest()


def establish(plan,value):
    out=Path(plan['output_directory']);namespace=key(value)
    Q.need(plan['cache_namespace']==namespace,'Exact206/build/ref/query/source namespace required')
    resume=plan.get('resume_output_directory')
    if resume is None:
        Q.need(not out.exists()and not plan.get('resume_actual_review_reference'),'Fresh namespace cannot reuse old caches or a resume approval')
        out.mkdir(parents=True);lock=(out/'adapter.lock').open('a+b')
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            marker=Q.write(out/NAME,dict(namespace_identity=namespace,binding=value,old_or_seeded_cache_used=False))
            return lock,marker,None
        except BaseException:lock.close();raise
    Q.need(Path(resume)==out and out.is_dir()and not out.is_symlink(),'Explicit same private resume stage required')
    # Read/verify marker BEFORE opening any writable file: an old201 stage has
    # no CPP marker and must be rejected without touching its directory.
    marker=Q.reference(out/NAME);actual=Q.load(out/NAME)
    Q.need(actual==dict(namespace_identity=namespace,binding=value,old_or_seeded_cache_used=False), 'Missing/foreign/changed backend cache namespace')
    review_ref=plan['resume_actual_review_reference'];review=authority.read(review_ref)
    Q.need(review['schema']=='ROOT_ALPHA_CPP_EXACT_CACHE_RESUME_ACTUAL_ACCEPTANCE_V1'
        and review['status']=='APPROVED_CLOSED_COMMITTED_SAME_NAMESPACE_CHECKPOINT'and review['reviewer']=='root'
        and review['namespace_manifest_reference']==marker and review['namespace_identity']==namespace
        and review['output_directory']==str(out)and review['all_previous_writers_gone']is True
        and review['closed_committed_checkpoint']is True and review['checkpoint_integrity_passed']is True
        and review['no_other_cache_seeded']is True,'Explicit independent Root closed checkpoint approval required')
    p=review['previous_actual_parent'];account=authority.read(review['previous_actual_accounting_reference'])
    Q.need(p['State']in('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED','SPECIAL_EXIT')
        and p['endpoint']==account['endpoint']==Q.ENDPOINT and str(p['UID'])=='1264'and p in account['actual_parents'],
        'Actual previous terminal parent/accounting, no live scientific retry')
    Q.verify(account['raw_sacct_reference'])
    db=review['query_cache_reference']
    Q.need(db['path']==str(out/'queries.sqlite')and not any((out/('queries.sqlite'+suffix)).exists()for suffix in('-journal','-wal','-shm')),
        'Closed committed cache and no active SQLite sidecars required')
    lock=(out/'adapter.lock').open('a+b')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with (out/'parent.lock').open('r+b')as parent:
            fcntl.flock(parent,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(parent,fcntl.LOCK_UN)
        Q.verify(db)  # Whole closed DB hash, under original quota Guard; never query live SQLite.
        return lock,marker,review_ref
    except BaseException:lock.close();raise
