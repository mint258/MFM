"""Producer/native execution facts for scoped equivalent-backend continuation."""
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from ..uff3_alpha_runtime_v1.terminal import parent
from ..alpha_sharded_novelty_v1.partition import assignment
from ..exact_nn_cached_v1 import engine as original
from ..exact_nn_inverted_cpp_v1 import backend

N=1196122


def read(ref):
    Q.need(type(ref['bytes'])is int and 0<=ref['bytes']<=2<<20,'Small native-equivalence metadata only')
    return Q.load(Q.verify(ref))


def previous_writers(plan,previous):
    """Called under original parent.lock, before reading any old score journals."""
    root=Path(plan['output_directory']);items=plan['resume_previous_allocations']
    Q.need(Path(plan['resume_output_directory'])==root and isinstance(items,list)and bool(items),
           'Explicit same-output resume and related real previous allocations required')
    for item in items:
        old=read(item['plan_reference']);proof=read(item['startup_proof_reference']);runtime=item['runtime']
        Q.need(proof['request']['producer_plan_reference']==item['plan_reference']
            and str(proof['job_id'])==str(runtime['job_id']) and proof['uid']==runtime['uid']==Q.UID
            and proof['endpoint']==runtime['endpoint']==Q.ENDPOINT and Path(old['output_directory'])==root,
            'Actual old writer same job/startup/plan/output identity; unrelated allocation is insufficient')
        parent(runtime,item['accounting_reference'],require_C0=False)
        same=dict(filtered_pool_reference=old['filtered_pool_reference'],reference=old['reference_manifest'],
            assigned_hash_buckets=assignment(old),partition_id=old['partition_id'],scope_key=old['scope_key'])
        Q.need(all(same[k]==previous[k]for k in same)
            and old['backend_adoption_reference'] in (previous['backend_adoption_reference'],plan['backend_adoption_reference']),
            'Previous writer has the identical five non-backend fields and only the proven equivalent implementations')
MAIN_SHA='2c1120a8b7428bf9c03429803f73a4334dde14bbbade3013991bcccf639cea23'
ALPHA_SHA='adb030f26717e19eb5f5d2127e69a5ecaa031460f1fbb02ab090001f02ad100b'
OLD206_SHA='9fb210c91522beedc1ac33f6d73ad9cf401be2d4f53f06788b5dd9e4b7cae516'
QUERY_SHA='1df7de435b7f131f3a2eb816919f33b3dfed10804cd86c04f850c06a278e4021'
HISTORICAL_SHA='6f20621f629cd23ba029aa25a04af9cb3cc05148e2cc15883dee6be6f78a054a'


def identity(ref):return(ref['bytes'],ref['sha256'])


def sacct(ref):
    path=Q.verify(ref);before=Q.frame(path);lines=path.read_text().splitlines()
    Q.need(lines and 'JobIDRaw'in lines[0].split('|'),'Native Slurm header required')
    names=lines[0].split('|');rows=[dict(zip(names,line.split('|')))for line in lines[1:]if line]
    Q.need(Q.frame(path)==before,'Native accounting changed during reading')
    return rows


def native_completion(main_ref,alpha_ref):
    main=sacct(main_ref);alpha=sacct(alpha_ref)
    one=lambda rows,job:[r for r in rows if r['JobIDRaw']==job]
    m=one(main,'4525827');a=one(alpha,'1885213');step=one(alpha,'1885213.0')
    Q.need(len(m)==1 and m[0]['UID']=='1278'and m[0]['State']=='COMPLETED'and m[0]['ExitCode']=='0:0'
        and int(m[0]['AllocCPUS'])==16 and any(r['JobIDRaw']=='4525827.batch'for r in main)
        and all(r['State']=='COMPLETED'and r['ExitCode']=='0:0'for r in main),
        'Actual Main4525827 UID1278 parent/batch C0, never relabelled Alpha execution')
    Q.need(len(a)==len(step)==1 and a[0]['UID']=='1264'and a[0]['State']=='RUNNING'
        and step[0]['State']=='COMPLETED'and step[0]['ExitCode']=='0:0'and int(step[0]['AllocCPUS'])==16,
        'Actual Alpha213.0 step C0; captured parent213 remains RUNNING, not falsely C0')


def benchmark(value,schema,uid,job):
    Q.need(value['schema']==schema and value['status']=='COMPLETE'and value['actual']['uid']==uid
        and value['actual']['job_id']==job and value['actual']['allocated_CPUs']==16
        and value['workers']==16 and value['reference_molecules_per_backend_per_worker']==N
        and value['query_identities']==64 and value['comparisons']==192 and value['repeats']==3
        and value['native_tests']==dict(errors=0,failures=0,passed=True,skips=0,tests=10)
        and value['current_old_new_all8_fields_and_F64_match']is True
        and value['historical206_all8_fields_and_F64_match']is True
        and value['old_and_new_load_order_alternates_by_worker']is True
        and value['paired_call_order_alternates_by_query_and_repeat']is True
        and value['QueryCache_used']is False and value['production_API_or_adoption_changed']is False
        and value['full_pool_speed_or_ETA_claimed']is False
        and value['prefix64_population_representativeness_claimed']is False
        and value['inputs']['queries']['sha256']==QUERY_SHA
        and value['inputs']['historical206']['sha256']==HISTORICAL_SHA,
        'Actual bounded full-reference paired native equivalence, not an all-query benchmark or adoption relabel')


def adopted(ref):
    """Consume producer/native facts directly. No new Root approval document."""
    Q.need(identity(ref)==(1858,'085ffef9529459d00f26a9eaad8cafa54790ac04719519a429d580a4fdff3fce'),
           'Actual immutable producer/native descriptor scoped to old206/ref196/filter209 required')
    proof=read(ref)
    Q.need(proof['schema']=='EXACT_INVERTED_NATIVE_EQUIVALENCE_V1'
        and proof['main_execution']==dict(endpoint='202.38.247.57:22',uid=1278)
        and identity(proof['main_result_reference'])==(28553,MAIN_SHA)
        and identity(proof['alpha_result_reference'])==(32092,ALPHA_SHA)
        and identity(proof['previous_backend_adoption_reference'])==(9317,OLD206_SHA),
        'Actual Main/Alpha producer bodies and old206 identity, no fabricated Root approval schema')
    main=read(proof['main_result_reference']);alpha=read(proof['alpha_result_reference'])
    native_completion(proof['main_native_sacct_reference'],proof['alpha_native_sacct_reference'])
    benchmark(main,'MAIN_FULL_COMMON_INVERTED_PAIRED64_BENCHMARK_V1',1278,'4525827')
    benchmark(alpha,'ALPHA_FULL_COMMON_INVERTED_PAIRED64_BENCHMARK_V1',1264,'1885213')
    Q.need(alpha['actual']['step_id']=='0'and alpha['actual']['parent_state_not_claimed_complete']is True
        and main['ordered_query_identity_sha256']==alpha['ordered_query_identity_sha256'],
        'Same ordered64 queries; Alpha native step does not claim its running parent complete')
    old=read(proof['previous_backend_adoption_reference']);packed=read(proof['reference_manifest_reference'])
    Q.need(old['reference_manifest_reference']==proof['reference_manifest_reference']
        and old['fingerprint_recipe']==original.RECIPE and old['mathematical_algorithm']==original.ALGORITHM
        and old['reference_molecules']==N and packed['schema']=='expansion_exact_ecfp4_reference_v1'
        and packed['status']=='COMPLETE'and packed['molecules']==N and packed['targets_present']is False
        and packed['fingerprint_recipe']==original.RECIPE
        and alpha['inputs']['fingerprints']==packed['fingerprints']
        and identity(main['inputs']['fingerprints'])==identity(packed['fingerprints'])
        and alpha['inputs']['historical206']==old['measurements_reference'],
        'Exactly old206/full196 reference and original mathematical domain across honest Main replica paths')
    filtered=read(proof['filtered_pool_reference'])
    Q.need(filtered['schema']=='PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1'and filtered['status']=='COMPLETE'
        and str(filtered['actual_parent']['job_id'])=='1885209'and filtered['actual_parent']['uid']==1264,
        'Equivalent-cache continuation scoped to the actual209 full filtered population')
    module,build=backend.load_kernel(alpha['builds']['new']);old_build=read(alpha['builds']['old'])
    Q.need(identity(alpha['builds']['new'])==(8197,'f75c6e879f251d67796325e0908e6f0bf9b293d20ae5909f86f4ebee5aa0488b')
        and build['oracle_source_reference']==Q.reference(original.__file__)
        and build['python']['version']==alpha['actual']['version']
        and module.build_info()==build['runtime_kernel_info']
        and module.build_info()['intersection_backend']=='CSR_BIT_POSTINGS_THEN_ORIGINAL_LOGICAL_GROUP_SCAN',
        'Actual Alpha-local binary/Core5/ABI/CPU identity; Main binary is not transported for execution')
    bodies=lambda refs:{Path(r['path']).name:identity(r)for r in refs}
    Q.need(bodies(old_build['source_references'])==bodies(old['validated_source_references'])
        and identity(build['oracle_source_reference'])==identity(old_build['oracle_source_reference']),
        'Freshly compiled old comparator is byte-identical old206 Core5 and mathematical oracle')
    for result in (main,alpha):
        sources={Path(r['path']).name:r for r in result['source_references']
                 if '/exact_nn_inverted_cpp_v1/'in r['path']and Path(r['path']).name in backend.SOURCES}
        Q.need(bodies(sources.values())==bodies(build['source_references'])
            and any(r==build['oracle_source_reference']for r in alpha['source_references']),
            'Both actual native producers bind exactly the current immutable inverted Core5/oracle bodies')
    Q.verify(alpha['inputs']['queries']);Q.verify(alpha['inputs']['historical206'])
    return {**proof,'native_equivalence_reference':ref,'build_manifest_reference':alpha['builds']['new'],
            'binary_reference':build['binary_reference']},packed