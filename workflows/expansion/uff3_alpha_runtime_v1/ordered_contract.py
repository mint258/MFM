"""Current fullIK/WP5-only sharded producer contracts, no Root approval gate."""
from ..alpha_runtime_v1 import common as Q
from .quality_authority import read
from .terminal import parent


def complete(rank,filtered,novelty):
    Q.need(filtered['schema']=='PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1'and filtered['status']=='COMPLETE'
        and set(filtered['policy']['identity_kinds'])=={'full','wp5'}
        and len(filtered['policy']['identity_kinds'])==2 and filtered['policy']['composition_veto']is False,
        'Current exact full InChIKey/WP5-only policy; old composition/all11 gates cannot be reused')
    candidates=filtered['candidates'];n=filtered['eligible_molecules']
    Q.need(type(n)is int and n>=10000000 and bool(candidates)
        and all(len(str(r['fp_bucket']))==1 and str(r['fp_bucket'])in'0123456789abcdef'for r in candidates)
        and all(type(r['rows'])is int and r['rows']>=0 for r in candidates)
        and sum(r['rows']for r in candidates)==n,'Complete candidate parts in legal FP buckets, no prefix/population narrowing')
    Q.need(novelty['schema']=='PUBCHEM_SHARDED_FULL_POOL_NOVELTY_V1'and novelty['status']=='COMPLETE'
        and novelty['queries']==n and novelty['filtered_pool_reference']==rank['filtered_pool']
        and bool(novelty['projection_parts']),'Same current complete all-pool novelty producer')
    Q.need(rank['schema']=='expansion_nested_queues_v1'
        and rank['status']=='CANDIDATE_ORDER_COMPLETE_NO_CONFORMERS_COMPUTED'
        and rank['pool_molecules']==n and rank['seed']==20261025
        and rank['queue_molecules_each']==5000000 and rank['first_batch_molecules_each']==1250000
        and rank['downstream_features_used']is False,'Actual original full10M R/N ordering and first2.5M')
    return candidates


def origin(plan,filtered):
    from ..pubchem_generic_recovery_overlay_v1.reader import validate_header
    pool=read(filtered['source_pool_receipt']);validate_header(pool)
    Q.need(filtered['population_version']==pool['population_version']
        and isinstance(plan['pubchem_version'],str)and bool(plan['pubchem_version']),
        'Frozen actual population and explicit nonempty PubChem source version')
    return dict(source_pool_receipt=filtered['source_pool_receipt'],original_source_projection=pool['original_source_projection'],
        source_snapshot_sha256=pool['source_snapshot_sha256'],population_version=pool['population_version'],
        pubchem_version=plan['pubchem_version'],feature_graph_field='isomeric_smiles',preserve_source_smiles=True,
        decontamination_policy=filtered['policy'],eval_exclusions=filtered['eval_exclusions'])


def completed_rank(plan,rank):
    binding=plan['ranking_completed'];runtime=binding['runtime']
    Q.need(rank['actual_parent']['job_id']==runtime['job_id']and rank['actual_parent']['uid']==runtime['uid']==Q.UID,
           'Same actual completed rank parent')
    parent(runtime,binding['accounting_reference'])
    proof=read(binding['startup_proof_reference'])
    Q.need(proof['request']['producer_plan_reference']==rank['resource_plan']
        and str(proof['job_id'])==str(runtime['job_id'])and proof['endpoint']==Q.ENDPOINT and proof['uid']==Q.UID,
        'Actual ranking startup/plan/C0 binds this receipt without a separate Root approval')

def completed_source(plan,manifest):
    b=plan['source_completed'];runtime=b['runtime'];p=manifest['actual_parent']
    Q.need(manifest['schema']=='PUBCHEM_UFF3_ORDERED_SOURCE_MANIFEST_V1'
        and manifest['status']=='ALL2500000_ORDERED_SOURCE_GRAPHS_PROJECTED_NO_UFF'
        and manifest['molecules']==2500000 and manifest['molecules_by_stream']=={'R':1250000,'N':1250000}
        and str(p['job_id'])==str(runtime['job_id'])and p['uid']==runtime['uid']==Q.UID,
        'Actual complete source projection parent, never a costpilot/prefix')
    parent(runtime,b['accounting_reference']);proof=read(b['startup_proof_reference'])
    Q.need(proof['request']['producer_plan_reference']==manifest['resource_plan']
        and str(proof['job_id'])==str(runtime['job_id'])and proof['endpoint']==Q.ENDPOINT and proof['uid']==Q.UID,
        'Actual source EOF producer/startup/terminal metadata, no manual approval')