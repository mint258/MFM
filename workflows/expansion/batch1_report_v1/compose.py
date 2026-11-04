"""Compose task2.9 from closed bounded evidence; never replay molecule files."""
import argparse
from decimal import Decimal,localcontext
import hashlib
import json
import os
from pathlib import Path
import stat
from .accounting import need,summarize,hours

MAX_BYTES=16<<20
REQUIRED={'registry','acquisition','funnel','pool','regression','filtered','novelty','rank','source','graph','closure','quality','pilot'}
GROUPS={'v1_common':1196122,'pubchem_1m':1000000,'R':1250000,'N':1250000}
SOURCES={'v1_all_roles_and_embargo','expansionrx','som_cyp','som_az','qm7','qm9','tdc_admet','moleculenet','marcel_drugs75k','marcel_kraken','coconut'}


def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()+b'\n'


def triple(ref):
    need(isinstance(ref,dict)and isinstance(ref.get('path'),str)and Path(ref['path']).is_absolute()
         and type(ref.get('bytes'))is int and ref['bytes']>=0
         and isinstance(ref.get('sha256'),str)and len(ref['sha256'])==64
         and all(c in'0123456789abcdef'for c in ref['sha256']),'Actual absolute path/bytes/lowercase SHA reference')
    return {key:ref[key]for key in('path','bytes','sha256')}


def frame(s):return(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


class Reader:
    def __init__(self,replicas=()):
        self.replicas={};self.reads={}
        for binding in replicas:
            original=triple(binding['source_reference']);replica=triple(binding['replica_reference'])
            need(original['bytes']==replica['bytes']and original['sha256']==replica['sha256'],'Replica must preserve original bytes/SHA')
            token=self.token(original);need(token not in self.replicas,'No duplicate replica mapping');self.replicas[token]=replica

    @staticmethod
    def token(ref):return json.dumps(triple(ref),sort_keys=True,separators=(',',':'))

    def bytes(self,ref):
        original=triple(ref);actual=self.replicas.get(self.token(original),original)
        need(actual['bytes']<=MAX_BYTES,'Bounded metadata/artifact only; do not open large DATA/catalogs')
        path=Path(actual['path']);before=path.lstat()
        need(stat.S_ISREG(before.st_mode)and before.st_size==actual['bytes'],'Closed regular input type/size')
        with path.open('rb')as stream:
            need(frame(os.fstat(stream.fileno()))==frame(before),'Same closed FD')
            raw=stream.read(MAX_BYTES+1);after=os.fstat(stream.fileno())
        need(frame(before)==frame(after)==frame(path.lstat())and len(raw)==actual['bytes']
             and hashlib.sha256(raw).hexdigest()==actual['sha256'],'Closed whole metadata SHA/frame')
        self.reads[self.token(original)]=dict(source_reference=original,actual_read_reference=actual,current_frame=list(frame(after)))
        return raw

    def json(self,ref):return json.loads(self.bytes(ref))


def get(document,pointer):
    need(pointer==''or pointer.startswith('/'),'Explicit JSON pointer')
    for part in pointer.split('/')[1:]:
        part=part.replace('~1','/').replace('~0','~');document=document[int(part)]if isinstance(document,list)else document[part]
    return document


def same(a,b):return triple(a)==triple(b)


def validate(doc,refs,reader):
    a,f,p,x,n,r,s,g,c,q,pilot=(doc[key]for key in('acquisition','funnel','pool','filtered','novelty','rank','source','graph','closure','quality','pilot'))
    need(a['schema']=='PUBCHEM_ACQUIRED_SOURCE_SNAPSHOT_V1'and a['status']=='ACQUISITION_AND_FULL_EOF_CID_INVENTORY_COMPLETE'
         and a['source_records']==f['source_rows']==p['source_rows']==124857440,'Actual complete official raw census')
    need(a['compressed_source']['sha256']==p['source_snapshot_sha256'],'Original official source snapshot SHA is the corrected pool source')
    need(f['schema']=='PUBCHEM_CLOSED_SCREENING_FUNNEL_V1'and f['fragment_count']==502
         and f['first_rule_counts_are_mutually_exclusive']is True and f['overlap_rule_counts_are_not_additive']is True
         and f['technical_UNKNOWN_is_not_chemical_exclusion']is True and same(f['pool_authority_reference'],refs['pool']),
         'Complete original502 first-failure and overlapping funnel metadata bound to corrected pool')
    original=f['original_source_counts'];current=f['corrected_source_counts'];recovered=f['recovered_original_technical_records']
    need(set(original)==set(current)=={'accepted','chemReject','technicalUnresolved'}and sum(original.values())==sum(current.values())==f['source_rows']
         and sum(f['chemical_first_rule_counts'].values())==original['chemReject']==current['chemReject']
         and current['accepted']-original['accepted']==original['technicalUnresolved']-current['technicalUnresolved']==recovered
         and p['source_counts']==current,'Chemical/technical/recovery mass conservation')
    need(p['schema']=='PUBCHEM_EXACT_MINCID_OVERLAY_POOL_V1'and p['status']=='MATERIALIZED_UNFILTERED_NO_RELEASE'
         and p['unique_full_keys']==f['unique_full_keys']and p['counts']['duplicate_fullkey_aliases']==f['duplicate_fullkey_aliases']
         and p['unique_full_keys']+f['duplicate_fullkey_aliases']==current['accepted'],'Complete corrected minCID/alias census')
    regression=doc['regression'];v=regression['result']
    need(regression['schema']=='ALPHA_COMMON_SELECTION_REGRESSION_BIND_PRODUCER_V1'and v['passed']is True
         and not v['failed_checks']and v['metrics']['agreement']>=.999
         and v['metrics']['boolean_counts']['unexplained']==0,'Actual source-bound original selection regression passed')
    need(x['schema']=='PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1'and x['status']=='COMPLETE'and same(x['source_pool_receipt'],refs['pool'])
         and x['input_unique_molecules']==p['unique_full_keys']==x['eligible_molecules']+x['excluded_molecules']
         and x['original_candidate_fields_and_types_preserved']is True,'Full current exact-key filter mass and source binding')
    policy=x['policy']
    need(set(policy['identity_kinds'])=={'full','wp5'}and len(policy['identity_kinds'])==2
         and policy['wp5_definition']=='InChIKey[:14]+":"+InChIKey[-1]'
         and all(policy[key]is False for key in('composition_veto','lower_bound_veto','wildcard_veto'))
         and policy['removed_subdatasets']=={'moleculenet':['PDBbind']},'Current user exact-structure-only policy')
    need(set(x['original_identity_source_dispositions'])==SOURCES,'Every current physical decontamination source included')
    for source in x['original_identity_source_dispositions'].values():
        need(sum(source['dispositions'].values())==source['original_identity_rows'],'Every physical source row disposition conserved')
    need(n['schema']=='PUBCHEM_SHARDED_FULL_POOL_NOVELTY_V1'and n['status']=='COMPLETE'
         and n['nearest_similarity_exact']is True and n['queries']==x['eligible_molecules']
         and same(n['filtered_pool_reference'],refs['filtered'])and n['reference_molecules']==1196122,'Complete full-pool exact NN, not query sample')
    need(r['schema']=='expansion_nested_queues_v1'and r['status']=='CANDIDATE_ORDER_COMPLETE_NO_CONFORMERS_COMPUTED'
         and r['queue_molecules_each']==5000000 and r['first_batch_molecules_each']==1250000
         and r['seed']==20261025 and r['downstream_features_used']is False and r['pool_molecules']==x['eligible_molecules']
         and same(r['filtered_pool'],refs['filtered'])and same(r['novelty_receipt'],refs['novelty']),
         'Actual nested10M R/N ordering with no downstream novelty features')
    need(s['schema']=='PUBCHEM_UFF3_ORDERED_SOURCE_MANIFEST_V1'and s['status']=='ALL2500000_ORDERED_SOURCE_GRAPHS_PROJECTED_NO_UFF'
         and s['molecules']==2500000 and s['molecules_by_stream']=={'R':1250000,'N':1250000}
         and same(s['ranking_receipt'],refs['rank'])and same(s['typed_filtered_pool'],refs['filtered']),
         'Complete actual first batch source and actual rank/filter lineage')
    need(g['schema']=='PUBCHEM_DISTRIBUTION_FOLLOWUP_REPORT_V1'and g['status']=='COMPLETE'
         and g['report_scope']=='TASK2_1_AND_TASK2_9_GRAPH_DISTRIBUTIONS','Complete graph report with actual before/after fixed1M')
    distribution=g['original_distribution_report']
    need(distribution['schema']=='EXPANSION_DISTRIBUTION_REPORT_RECEIPT_V1'
         and distribution['status']=='ALL_REQUIRED_DISTRIBUTION_NUMERICS_AND_FIGURES_COMPLETE'
         and distribution['augmented_reference_before_after_complete']is True,'Complete counted tables/figures, not baseline-only')
    artifacts={Path(ref['path']).name:ref for ref in distribution['artifacts']}
    need(len(artifacts)==len(distribution['artifacts'])and 'summary.json'in artifacts,'Unique graph artifact names/actual summary')
    summary=reader.json(artifacts['summary.json'])
    need(summary['schema']=='EXPANSION_DISTRIBUTION_COUNTED_SUMMARY_V1'
         and summary['status']=='ALL_REQUIRED_NUMERICAL_POPULATIONS_AND_EXACT_COVERAGE_COMPLETE'
         and summary['populations']==GROUPS and summary['coverage_gain']['same_queries']==1000000
         and summary['coverage_gain']['minimum_similarity_gain']>=0,'All four complete populations and same1M exact coverage')
    for group in('R','N'):
        pop=reader.json(distribution['population_manifest_references'][group])
        need(same(pop['authority_reference'],refs['source'])and pop['expected_molecules']==1250000,'R/N graph statistics bind the actual delivered source')
    coverage_rows=[]
    for role in('before','after'):
        coverage=reader.json(g[role+'_coverage_reference'])
        need(coverage['schema']=='EXPANSION_EXACT_SCIENTIFIC_COVERAGE_V1'and coverage['status']=='COMPLETE'
             and coverage['queries']==coverage['projection']['rows']==1000000 and coverage['nearest_similarity_exact']is True
             and coverage['reference_role']==role and coverage['reference_molecules']==(1196122 if role=='before' else 3696122),
             'Actual complete fixed1M coverage receipt, never raw cost/partial schema relabel')
        coverage_rows.append(coverage)
    need(coverage_rows[0]['baseline_receipt']==coverage_rows[1]['baseline_receipt'],'Before/after use the identical frozen1M baseline')
    need(c['schema']=='PUBCHEM_UFF3_CANDIDATE_STORAGE_CLOSURE_V1'and c['status']=='COMPLETE_CANDIDATE_DATASET_NOT_TRAINING_RELEASE'
         and c['maximum_delivered_conformers']==3 and same(c['source_manifest'],refs['source'])
         and same(c['qa_report_reference'],refs['quality'])and c['full_source_bidirectional_identity_and_rank_closure']is True
         and c['saved_D20_D3_and_coordinate_F64_bits_equal_delivered_families']is True,'Complete actual candidate storage closure')
    metrics=c['report_metrics'];allgroups=[row for row in metrics['groups']if row['group_type']=='all']
    need(metrics['schema']=='PUBCHEM_UFF3_FINAL_REPORT_METRICS_V1'and metrics['status']=='COMPLETE_SAVED_METADATA_ONLY'
         and metrics['molecules']==2500000 and len(allgroups)==1,'Closed finalizer report metrics required; no perMID replay fallback')
    total=allgroups[0];bins=total['delivery_molecules'];stats=c['logical_census_and_saved_evidence']
    need(set(bins)=={'0','1','2','3','UNKNOWN'}and sum(bins.values())==2500000
         and sum(int(k)*bins[k]for k in('0','1','2','3'))==total['known_actual_conformer_denominator']==stats['actual_exported_conformers']
         and bins['UNKNOWN']==stats['unknown_actual_export_count_molecules'],'Actual delivery0/1/2/3/UNKNOWN and conformer denominator')
    need(q['schema']=='PUBCHEM_UFF3_VALIDITY_REVIEW_V1'and q['mode']=='full'
         and q['status']=='COMPLETE_ORIGINAL_MASK_AND_ROBUST_REVIEW_REPORT'
         and q['source_molecules_by_stream']=={'R':1250000,'N':1250000}
         and q['source_state_counts']==stats['source_state_counts']and q['new_R_N_TRAIN_fit']is False,'Original full masks/QA reused unchanged')
    need(len(q['all_stream_field_counts'])==len({str(v['field_id'])for v in q['all_stream_field_counts']})==27,
         'All27 original D field record-mask summaries required')
    for field in q['all_stream_field_counts']:
        need(0<=field['newly_masked_records']<=field['canonical_records']and 100*field['newly_masked_records']<=field['canonical_records'],
             'Original strict>1% new-record-mask stop condition unresolved')
    need(pilot['schema']=='PUBCHEM_UFF3_ALLOCATION_RECEIPT_V1'and pilot['mode']=='pilot'
         and pilot['status']=='COMPLETE_CANDIDATE_PILOT_NOT_TRAINING_RELEASE'
         and pilot['expected_molecules']==pilot['closed_family_export_molecules']==10000
         and pilot['maximum_conformers']==3 and same(pilot['source_manifest'],refs['source'])
         and pilot['recipe_sha256']==c['recipe_sha256'],'Actual frozen10k pilot evidence')
    return summary,artifacts,total


def link(ref,label=None):return '[%s](%s)'%(label or Path(ref['path']).name,ref['path'].replace(' ','%20'))


def table(headers,rows):
    clean=lambda value:str(value).replace('|','\\|').replace('\n',' ')
    return ['| '+' | '.join(headers)+' |','|'+'|'.join('---'for _ in headers)+'|']+['| '+' | '.join(clean(v)for v in row)+' |'for row in rows]


def ratio(numerator,denominator):
    with localcontext()as context:
        context.prec=40
        return format(Decimal(numerator)/Decimal(denominator),'f')


def pilot_summary(pilot,metrics,native_parent):
    """Observed allocations and optional already-counted timings; no new gate/read."""
    seconds=native_parent['allocated_core_seconds'];job=pilot.get('runtime',{}).get('job_id')
    result=dict(pilot_molecules=10000,pilot_allocated_core_seconds=seconds,
        allocated_core_seconds_per_source_molecule=ratio(seconds,10000),
        all_failed_sparse_and_unknown_sources_in_cost_denominator=True,
        projected2500000_allocated_core_seconds=seconds*250,
        projected2500000_allocated_core_hours=hours(seconds*250),scale=250,
        is_rough_extrapolation_not_actual_full_cost_or_authorization=True,
        assumptions='Comparable balanced R/N size and throughput; startup/I/O overhead may amortize differently at full scale.',
        pilot_native_job_id=None if job is None else str(job),timing_status='UNAVAILABLE_NO_UNIQUE_PILOT_PRODUCER_GROUP',
        recorded_group_molecules=None,delivery_molecules=None,known_retained_conformers=None,native_operations={})
    groups=[row for row in metrics.get('groups',[])if row.get('group_type')=='producer_job'
            and job is not None and str(row.get('producer_job_id'))==str(job)]
    if len(groups)!=1:return result
    group=groups[0];count=group['molecules'];bins=group['delivery_molecules'];denominator=group['known_actual_conformer_denominator']
    whole=count==10000 and sum(bins.values())==10000
    result.update(timing_status='COMPLETE_PILOT_METADATA_GROUP'if whole else'PARTIAL_OR_MIXED_PRODUCER_GROUP',
        recorded_group_molecules=count,delivery_molecules=bins,known_retained_conformers=denominator)
    for operation,value in group.get('native_call_timings',{}).items():
        calls=value.get('measured_calls',0);wall=value.get('wall_nanoseconds');observed=value.get('known_actual_conformers_in_measured_call_molecules',0)
        status='UNAVAILABLE_UNMEASURED';average=None
        if calls and wall is not None:
            if bins.get('UNKNOWN',0)>0:status='UNAVAILABLE_UNKNOWN_DELIVERY'
            elif observed<=0:status='UNAVAILABLE_NO_KNOWN_RETAINED_CONFORMERS'
            else:
                complete=(whole and group.get('journal_unavailable_molecules')==0
                    and group.get('molecules_without_measured_call_timings')==0
                    and value.get('return_events_without_timing')==0
                    and observed==denominator)
                status='COMPLETE_RECORDED_TIMING'if complete else'PARTIAL_RECORDED_TIMING'
                average=ratio(wall,observed)
        result['native_operations'][operation]=dict(status=status,measured_calls=calls,wall_nanoseconds=wall,
            known_retained_conformers_in_measured_call_molecules=observed,
            wall_nanoseconds_per_known_retained_conformer=average,
            is_observed_workload_per_retained_conformer_not_one_optimizer_attempt=True)
    return result


def render(doc,refs,summary,artifacts,total,cost,local_artifacts):
    f=doc['funnel'];p=doc['pool'];x=doc['filtered'];c=doc['closure'];q=doc['quality'];metrics=c['report_metrics']
    lines=['# PubChem expansion: first-batch report','','This report composes actual closed producer evidence for task2.9. It reports all2.5M candidate sources, including sparse, failed and UNKNOWN records; it is not a training release.','',
           '## Source, rules and regression','',
           'The official CID–SMILES snapshot contains %s source rows. Original raw UNKNOWN records and the previous population/sample remain immutable; the corrected population is `%s`.'%(f"{f['source_rows']:,}",p['population_version']),
           'Canonical decontamination source registry: %s. Acquisition: %s. Exact source-bound original-selection regression: %s (agreement %s; unexplained0).'%(link(refs['registry']),link(refs['acquisition']),link(refs['regression']),doc['regression']['result']['metrics']['agreement']),'',
           '## Screening funnel','']
    rows=[('Raw CID–SMILES records',f['source_rows'])]
    rows += [('Chemical reject, first failing '+rule,n)for rule,n in f['chemical_first_rule_counts'].items()]
    rows += [('Original accepted',f['original_source_counts']['accepted']),('Original technical UNKNOWN',f['original_source_counts']['technicalUnresolved']),
        ('Accepted by technical generic-representation recovery',f['recovered_original_technical_records']),
        ('Corrected accepted aliases',f['corrected_source_counts']['accepted']),('Remaining technical UNKNOWN',f['corrected_source_counts']['technicalUnresolved']),
        ('Internal duplicate full-key aliases',f['duplicate_fullkey_aliases']),('Unique minimum-CID full keys',p['unique_full_keys']),
        ('Excluded by current exact structure decontamination',x['excluded_molecules']),('Complete eligible population',x['eligible_molecules']),
        ('Frozen ordered queues (R + N)',10000000),('Actual first batch (R + N)',2500000)]
    lines+=table(['Stage / disposition','Molecules / source rows'],rows)
    lines+=['','Chemical first-rule rows are mutually exclusive; overlapping hits below are not additive. Technical UNKNOWN is never counted as chemical rejection. Original technical reasons precede recovery and may overlap.','']
    lines+=table(['Rule','Overlapping chemical hits'],f['chemical_overlap_rule_counts'].items())
    lines+=['','## Decontamination evidence','',
        'Only complete InChIKey and original WP5 (`InChIKey[:14]+":"+InChIKey[-1]`) equality vetoes are used. Composition, lower bounds and wildcard vetoes are absent. PDBbind is outside the downstream plan; unresolved structures emit no structural veto and remain excluded from downstream evaluation with original row/source evidence. Source splits/roles are preserved.','']
    lines+=table(['Physical source','Identity rows','Exact-keyed','Other recorded dispositions'],[(name,value['original_identity_rows'],value['dispositions'].get('EXACT_KEYED',0),json.dumps({k:n for k,n in value['dispositions'].items()if k!='EXACT_KEYED'},sort_keys=True))for name,value in sorted(x['original_identity_source_dispositions'].items())])
    lines+=['','Index: %s; complete evaluation-exclusion audit: %s. Exclusion hits across sources are not a partition of removed candidates.'%(link(x['exact_index']),link(x['eval_exclusions'])),
        '','## R/N distributions and exact coverage','',
        'R and N each contain1.25M molecules. Both are compared with full Common TRAIN/VAL and the same fixed-seed, same-X, internally deduplicated pre-decontamination PubChem1M sample. No sampled Common or UFF-success-only graph cohort is substituted. R/N selection uses original v1-only novelty mathematics and no downstream features.','']
    lines+=table(['Population','Molecules','Distinct scaffolds','Singleton scaffolds'],[(name,n,summary['scaffold_long_tail'][name]['distinct_scaffolds'],summary['scaffold_long_tail'][name]['singleton_scaffolds'])for name,n in summary['populations'].items()])
    numeric={}
    for row in summary['numeric']:
        if row['population_or_comparison']in GROUPS:numeric.setdefault(row['field'],{})[row['population_or_comparison']]=row['mean']
    lines+=['']+table(['Descriptor mean','Common','PubChem1M','R','N'],[(name,*(format(values[group],'.8g')for group in('v1_common','pubchem_1m','R','N')))for name,values in sorted(numeric.items())if set(values)==set(GROUPS)])
    for name in('descriptor_distributions.png','elements_and_scaffold_long_tail.png','functional_group_prevalence.png','exact_nearest_coverage_before_after.png'):
        need(name in local_artifacts,'Actual required scientific figure missing');lines+=['','![%s](batch1_figures/%s)'%(name,name)]
    gain=summary['coverage_gain']
    lines+=['','On the identical1M query identities, mean exact nearest-Tanimoto gain is %s; %s queries strictly improve; minimum gain is %s.'%(gain['mean_similarity_gain'],gain['queries_with_strictly_improved_coverage'],gain['minimum_similarity_gain']),
        'Exact full-identity/self matches remain included and are reported separately from Tanimoto=1 fingerprint matches: `%s`.'%json.dumps(summary['identity_match_counts'],sort_keys=True),
        'All numerical moments, full categorical counts, functional groups, scaffold/ring/element/size strata and fixed-bin ECDF tables are bound in the graph report %s. Displayed ECDFs are fixed-bin curves, not unbinned estimates.'%link(refs['graph']),
        '','## UFF/D delivery, failures and timings','',
        'The frozen recipe allows at most3 actual conformers, fixed seed/order and0.5Å deduplication, with no fill or retry; D20 is graph-level and D3/atom-SASA use each actual delivered conformer. Internal candidates/optimizer attempts are separate from delivered conformers.','']
    lines+=table(['Actual delivered conformers','Molecules'],total['delivery_molecules'].items())
    lines+=['']+table(['Stream','Delivered0','Delivered1','Delivered2','Delivered3','UNKNOWN','Known delivered conformers'],
        [(row['stream'],*(row['delivery_molecules'][key]for key in('0','1','2','3','UNKNOWN')),row['known_actual_conformer_denominator'])
         for row in metrics['groups']if row['group_type']=='stream'])
    known=total['known_delivery_molecules'];positive=known-total['delivery_molecules']['0']
    lines+=['','Molecules with at least one known delivered conformer: %s/%s known-delivery molecules (%s of all2.5M); UNKNOWN is %s and is not zero. Sparse positive delivery alone is not classified as failure.'%(positive,known,positive,total['delivery_molecules']['UNKNOWN']),
        'Actual delivered conformer denominator: %s. Original D20 source evidence states: `%s`.'%(total['known_actual_conformer_denominator'],json.dumps(c['logical_census_and_saved_evidence']['D20_evidence_state_counts'],sort_keys=True)),'']
    lines+=table(['Original source state','Molecules'],total['source_state_counts'].items())
    lines+=['']+table(['Measured original operation','Calls','Raised calls','Wall ns','Process CPU ns','Known delivered conformers in measured-call molecules'],[(name,v['measured_calls'],v['raised_calls'],v['wall_nanoseconds'],v['process_CPU_nanoseconds'],v['known_actual_conformers_in_measured_call_molecules'])for name,v in total['native_call_timings'].items()])
    lines+=['']+table(['Stored worker/generation clock','Measured molecules','Unavailable molecules','Summed seconds'],[(name,v['observed_molecules'],v['unavailable_molecules'],v['total_seconds_decimal'])for name,v in total['stored_worker_or_generation_clocks'].items()])
    lines+=['']+table(['Historical recorded cache quantity','Observed molecules','Unavailable molecules','Recorded sum'],[(name,v['observed_molecules'],v['unavailable_molecules'],v['sum_recorded_values'])for name,v in total['recorded_cache_counts'].items()])
    lines+=['','Per-call times cover only recorded native invocations and exclude journal fsync. Legacy unmeasured clocks remain null; recorded cache counts and generation elapsed time may predate the current producer when reused. Prepare is not an inferred successful D20 call. Successful native returns without matching return events remain distinct from native exceptions.','',
        'Complete R/N/job timing summaries and per-MID attempts/optimizer codes/stereo/error pointers are in the finalizer metrics. Raw errors stay in pinned original cache/packet/journal, without being copied into this report.','']
    lines+=table(['Diagnostic domain','Code','Observed count (not necessarily unique molecules)'],[(v['domain'],v['code'],v['count'])for v in total['diagnostic_code_top20']])
    lines+=['','Metrics catalogs: '+', '.join(link(ref,name)for name,ref in metrics['catalogs'].items())+'.',
        'QA preserves original masks and TRAIN calibration without fitting R/N; source NA is separate from newly masked records. Worst20 and complete reason sets: %s; %s.'%(link(q['worst20_per_field']),link(q['mask_reason_sets'])),'']
    lines+=table(['D field','Canonical records','Newly masked records','Original/source-ineligible records'],[(v.get('field_key',v['field_id']),v['canonical_records'],v['newly_masked_records'],v['source_ineligible_records'])for v in q['all_stream_field_counts']])
    lines+=['','## Actual allocation cost and storage','',
        'Native allocated cost is **%s core-hours** (%s core-seconds), summed once per distinct terminal parent as `ElapsedRaw × AllocCPUS /3600`. Batch/extern steps are not added again. Failed, cancelled, diagnostic and superseded attempts remain included. TotalCPU and measured kernel process CPU are separate observations.'%(cost['allocated_core_hours'],cost['allocated_core_seconds']),
        'Declared accounting scope: '+cost['coverage_statement'],'']
    lines+=table(['Stage','Parents','Allocated core-hours','Observed TotalCPU seconds','Parents without TotalCPU'],[(v['group'],v['parents'],v['allocated_core_hours'],v['observed_TotalCPU_seconds_decimal'],v['TotalCPU_unavailable_parents'])for v in cost['groups']if v['group_type']=='stage'])
    pilot_cost=cost['pilot_native_parent']
    pilot_metrics=pilot_summary(doc['pilot'],metrics,pilot_cost)
    lines+=['','The selected closed10k pilot parent `%s` used %s allocated core-hours (%s core-seconds); its observed TotalCPU is %s CPU-seconds. This selected-parent observation is separate from failed/superseded attempts, which remain in the complete cost inventory.'%(pilot_cost['job_id'],pilot_cost['allocated_core_hours'],pilot_cost['allocated_core_seconds'],pilot_cost['TotalCPU_seconds_decimal']),
        'Pilot allocated cost per source molecule is %s core-seconds, with all10,000 failed/sparse/UNKNOWN outcomes retained in that denominator. Multiplying the observed pilot allocation by250 gives a rough2.5M forecast of %s allocated core-hours. This assumes comparable balanced R/N size and throughput; full-scale startup/I/O overhead amortization can differ. It is not actual full-batch cost or authorization; the actual complete allocation inventory above is authoritative.'%(pilot_metrics['allocated_core_seconds_per_source_molecule'],pilot_metrics['projected2500000_allocated_core_hours']),
        'Optional pilot journal metrics: `%s`; recorded group molecules=%s, known retained conformers=%s, delivery bins=%s. Missing/partial producer groups or unmeasured legacy timings are not filled with zero.'%(pilot_metrics['timing_status'],pilot_metrics['recorded_group_molecules'],pilot_metrics['known_retained_conformers'],json.dumps(pilot_metrics['delivery_molecules'],sort_keys=True)),
        'Every native parent/state/exit/allocation row is preserved in batch1_report.json. Original10k pilot: %s. No kernel-time sum is presented as cluster allocation cost.'%link(refs['pilot']),'']
    lines+=table(['Pilot native operation','Measurement coverage','Measured calls','Known retained conformer denominator','Wall ns per known retained conformer'],[(name,v['status'],v['measured_calls'],v['known_retained_conformers_in_measured_call_molecules'],v['wall_nanoseconds_per_known_retained_conformer'])for name,v in pilot_metrics['native_operations'].items()])
    lines+=['','Pilot per-conformer averages divide only measured operation wall time by retained conformers in those measured-call molecules; they include internal unsuccessful attempts in the observed workload. Partial measurements are labelled; UNKNOWN delivery makes the average unavailable. These are not allocated core-seconds or optimizer-attempt averages. A native sacct TotalCPU of00:00 is the recorded scheduler observation and does not establish zero actual CPU use.','']
    storage=c['storage']
    lines+=table(['Storage category','Logical file bytes','Actual allocated bytes'],[(v['category'],v['logical_file_bytes'],v['actual_allocated_blocks_bytes'])for v in storage['categories']])
    lines+=['','Storage is inode-deduplicated within the finalizer census; shared/fixed inputs, QA and finalizer scratch are separate categories. Finalizer own closed SQL/catalog allocated bytes: %s. These per-scope censuses are not blindly added into a global filesystem-unique total.'%c['finalizer_own_closed_sql_and_catalog_allocated_bytes']]
    projection=storage['linear10M_projection']
    lines+=['','10M variable-only storage projection: '+(json.dumps(projection,sort_keys=True)if projection is not None else'unavailable because cross-category shared inodes prevent unambiguous attribution')+'.',
        'Only measured variable UFF/D family and retained molecule evidence/directory costs are multiplied4×. Full-pool NN, ranking, Common/calibration/shared inputs and QA/finalizer SQL are not scaled. This assumes the same R/N size/sparsity/compression distribution; it is neither measured10M storage nor authorization to generate10M.',
        '','## Provenance and limits','',
        'batch1_report.json retains exact input references, metadata-read frames, all accounted parents and catalog/graph references. This composer hashes only bounded metadata and copied figures; it does not rehash large catalog/DATA bodies, reread2.5M directories, rerun chemistry, refit masks or change selection. Complete producer outputs and terminal accounting are required; no future hash or pending output is treated as complete.','',
        'UNKNOWN and sparse scientific outcomes remain explicit. Complete evidence reporting is not a claim that every descriptor succeeded, nor a training-release decision. Accounting completeness is for the explicitly declared goal inventory, not an audit of unrelated account jobs.','']
    return '\n'.join(lines)


def run(config_path,output):
    config_path=Path(config_path);before=config_path.lstat()
    need(stat.S_ISREG(before.st_mode)and before.st_size<=MAX_BYTES,'Bounded ordinary composer config')
    with config_path.open('rb')as stream:
        need(frame(os.fstat(stream.fileno()))==frame(before),'Same config FD')
        raw=stream.read(MAX_BYTES+1);after=os.fstat(stream.fileno())
    need(frame(before)==frame(after)==frame(config_path.lstat())and len(raw)==before.st_size,'Stable bounded composer config')
    config=json.loads(raw);need(config['schema']=='PUBCHEM_BATCH1_REPORT_CONFIG_V1'and set(config['inputs'])==REQUIRED,'Explicit actual complete input set')
    reader=Reader(config.get('replicas',[]));refs=config['inputs'];doc={name:reader.json(ref)for name,ref in refs.items()}
    # Optional additional actual original registry/recipe pins. No new approval
    # or invented source schema is required for older provenance documents.
    for binding in config.get('reference_bindings',[]):
        need(same(get(doc[binding['input']],binding['pointer']),refs[binding['equals_input']]),'Original producer reference binding differs')
    summary,artifacts,total=validate(doc,refs,reader)
    inventory=reader.json(config['accounting_inventory_reference']);cost=summarize(inventory,reader)
    expected=[refs[name]for name in('regression','filtered','rank','source','graph','closure','quality','pilot')]
    expected+=doc['novelty']['partition_manifest_references']+doc['closure']['generation_receipts']
    expected+=[doc['graph'][role+'_coverage_reference']for role in('before','after')]
    bound=set()
    for binding in config['producer_accounting_bindings']:
        producer_ref=binding['producer_reference'];producer=reader.json(producer_ref);bound.add(reader.token(producer_ref))
        if 'startup_proof_reference'in binding:
            proof=reader.json(binding['startup_proof_reference'])
            need(same(proof['request']['producer_plan_reference'],get(producer,binding['plan_pointer']))
                 and proof['endpoint']==binding['endpoint']and proof['uid']==binding['uid'],
                 'Original startup identity/plan binds receipt without embedded job ID')
            job=str(proof['job_id'])
        else:job=str(get(producer,binding['job_pointer']))
        matches=[row for row in cost['parents']if row['endpoint']==binding['endpoint']and row['uid']==binding['uid']and row['job_id']==job]
        need(len(matches)==1 and matches[0]['disposition']=='adopted'and matches[0]['state']=='COMPLETED'
             and matches[0]['exit_code']=='0:0','Every actual adopted producer is included in terminal native cost inventory')
        if same(producer_ref,refs['pilot']):cost['pilot_native_parent']=matches[0]
    need({reader.token(ref)for ref in expected}<=bound,'All final producer, NN partitions, generation and before/after native parents bound')
    for group in doc['closure']['report_metrics']['groups']:
        if group['group_type']=='producer_job'and group['producer_job_id']is not None:
            need(any(row['endpoint']=='218.192.171.238:22'and row['uid']==1264
                     and row['job_id']==str(group['producer_job_id'])for row in cost['parents']),
                 'Retained outputs from older/failed producer jobs must not lose their actual allocation cost')
    output=Path(output);need(not output.exists(),'Fresh report output directory; do not overwrite history');output.mkdir(parents=True)
    figures=output/'batch1_figures';figures.mkdir();local={}
    for name,ref in artifacts.items():
        if Path(name).suffix in('.png','.pdf'):
            body=reader.bytes(ref);path=figures/name
            with path.open('xb')as stream:stream.write(body)
            local[name]=dict(path=str(path),bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),original_reference=ref)
    text=render(doc,refs,summary,artifacts,total,cost,local)
    report=output/'batch1_report.md';report.write_text(text,encoding='utf-8')
    manifest=dict(schema='PUBCHEM_BATCH1_COMPLETE_EVIDENCE_REPORT_V1',status='TASK2_9_EVIDENCE_COMPLETE_NOT_TRAINING_RELEASE',
        config_reference=dict(path=str(config_path.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),inputs=refs,
        accounting_inventory_reference=config['accounting_inventory_reference'],accounting=cost,
        pilot_reporting=pilot_summary(doc['pilot'],doc['closure']['report_metrics'],cost['pilot_native_parent']),
        graph_artifacts=artifacts,copied_figures=local,report_metrics=doc['closure']['report_metrics'],
        graph_population_counts=summary['populations'],coverage_gain=summary['coverage_gain'],
        metadata_reads=list(reader.reads.values()),large_DATA_or_per_MID_reads=0,new_scientific_calls=0,
        report_reference=dict(path=str(report),bytes=report.stat().st_size,sha256=hashlib.sha256(report.read_bytes()).hexdigest()),
        source_references=[dict(path=str(path.resolve()),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())for path in sorted(Path(__file__).parent.glob('*.py'))])
    with(output/'batch1_report.json').open('xb')as stream:stream.write(canonical(manifest))
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True,type=Path);parser.add_argument('--output-directory',required=True,type=Path)
    args=parser.parse_args();result=run(args.config,args.output_directory)
    print(json.dumps(dict(report=result['report_reference'],status=result['status'])))


if __name__=='__main__':main()
