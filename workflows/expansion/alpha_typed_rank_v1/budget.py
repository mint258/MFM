"""Root-reviewed private exact partitions; legacy blocks are never omitted."""
from pathlib import Path
from ..alpha_runtime_v1 import common as Q


def choose(review,global_budget,key):
    Q.need(review['schema']=='ROOT_ALPHA_PRIVATE_EXACT_BUDGET_PARTITION_ACTUAL_REVIEW_V1'
      and review['status']=='APPROVED_PRIVATE_EXACT_PARTITIONS' and review['reviewer']=='root'
      and review['endpoint']==global_budget['endpoint']==Q.ENDPOINT and review['uid']==global_budget['uid']==1264
      and global_budget['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2' and global_budget['reviewer']=='root'
      and review['quota_root']==global_budget['quota_root'],'Actual Root Alpha global/private partition review required')
    aggregate=Path(review['aggregate_scope_root']);Q.need(aggregate==Path('/gfshome/alpha/pubchem_expansion_20261103/exact'),
      'Actual aggregate exact namespace required')
    legacy=review['closed_legacy_scopes'];parts=review['partitions'];old=review['closed_legacy_allocated_bytes']
    Q.need(type(old)is int and old>=0 and old==sum(r['allocated_bytes']for r in legacy)
      and review['closed_legacy_writers_gone']is True and review['closed_legacy_own_disjoint']is True,
      'Legacy B must be an explicit actual closed own physical census, not an omitted/default zero')
    Q.need(review['closed_legacy_scope_census_reference'] and (old==0 or review['closed_legacy_actual_accounting_references']),
      'Actual legacy census and terminal-writer accounting references required')
    roots=[]
    for row in legacy:
        path=Path(row['path']);Q.need(path.is_absolute()and path.is_relative_to(aggregate)and path!=aggregate
          and type(row['allocated_bytes'])is int and row['allocated_bytes']>=0
          and row['owned_uid']==1264 and row['all_writers_gone']is True,'Actual disjoint own legacy scope metadata required')
        roots.append(path)
    names=set();total=0
    for row in parts:
        path=Path(row['output_scope_root']);cap=row['output_cap_bytes'];credit=row['allocated_bytes_credit']
        Q.need(row['partition_key']not in names and path.is_absolute()and path.is_relative_to(aggregate)and path!=aggregate
          and type(cap)is int and cap>0 and type(credit)is int and 0<=credit<=cap
          and row['remaining_reserved_bytes']==cap-credit,'Each actual private scope needs exact cap/credit/remaining arithmetic')
        if credit:Q.need(row['physical_census_reference'],'Positive partition physical credit needs actual census reference')
        names.add(row['partition_key']);roots.append(path);total+=cap
    Q.need(all(not(a==b or a.is_relative_to(b)or b.is_relative_to(a))for i,a in enumerate(roots)for b in roots[i+1:]),
      'Closed legacy and all new private partitions must be disjoint')
    Q.need(total==review['partition_cap_total_bytes'] and old+total<=global_budget['scope_total_caps_bytes']['exact'],
      'Actual legacy B plus all partition caps must fit the real global exact cap')
    nonexact=sum(max(0,cap-global_budget['closed_credit_bytes_by_scope'].get(scope,0))
      for scope,cap in global_budget['scope_total_caps_bytes'].items()if scope!='exact')
    Q.need(review['nonexact_remaining_reserved_bytes']==nonexact and review['all_other_goals_and_exact_partitions_reserved']is True,
      'All nonexact remaining reservations must match actual global cap-minus-closed-credit arithmetic')
    selected=[r for r in parts if r['partition_key']==key];Q.need(len(selected)==1,'Exactly one chosen actual private partition')
    chosen=selected[0];others=sum(r['remaining_reserved_bytes']for r in parts if r['partition_key']!=key)
    Q.need(type(chosen['other_future_reserved_bytes'])is int and chosen['other_future_reserved_bytes']>=nonexact+others
      and chosen['minimum_free_bytes']==global_budget['minimum_free_after_all_future_bytes'],
      'Other futures include nonexact and peer-partition remaining amounts; closed legacy B is already used, not future reserve')
    return chosen
