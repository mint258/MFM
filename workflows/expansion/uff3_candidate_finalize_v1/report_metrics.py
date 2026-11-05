"""Reporting metadata from already verified saved objects, without native calls."""
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

OPERATIONS = ('prepare', 'embed', 'optimize', 'd3')
RETURN_PHASES = {'graph_return':'prepare', 'embedding_return':'embed',
                 'optimizer_return':'optimize', 'descriptor_return':'d3'}
METADATA_KEY = '_report_metrics'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def error(value, pointer):
    if value is None: return None
    raw = value if isinstance(value, str) else canonical(value)
    head = raw.split(':', 1)[0]
    code = head if 0 < len(head) <= 96 and all(c.isalnum() or c in '_.-' for c in head) else 'MESSAGE_WITHOUT_SHORT_TYPE_CODE'
    return dict(code=code, value_sha256=hashlib.sha256(raw.encode()).hexdigest(), source_pointer=pointer)


def scalar(value):
    text = canonical(value)
    return text if len(text) <= 96 else 'NONSHORT_SCALAR_METADATA'


def extract(source, manifest, cache, packet, journal, saved):
    """All arguments were already read/validated by closed.read_one. Mutates none."""
    calls = []; seen = set(); flags = []; missing = Counter(); counts = Counter(); attempt_details = []
    for ordinal, event in enumerate(journal or []):
        operation = RETURN_PHASES.get(event.get('phase'))
        if operation and 'native_call_timing' not in event: missing[operation] += 1
        values = []
        if 'native_call_timing' in event:
            values.append((event['native_call_timing'], True, None))
        values.extend((value, False, index) for index, value in enumerate(event.get('native_call_timings_without_matching_return', [])))
        for timing, matched, index in values:
            valid = (isinstance(timing, dict) and timing.get('operation') in OPERATIONS
                and type(timing.get('wall_nanoseconds')) is int and timing['wall_nanoseconds'] >= 0
                and type(timing.get('process_CPU_nanoseconds')) is int and timing['process_CPU_nanoseconds'] >= 0
                and type(timing.get('returned')) is bool
                and (timing.get('error_type') is None or isinstance(timing.get('error_type'), str)))
            if not valid or matched and timing['operation'] != operation:
                flags.append(dict(code='INVALID_OR_MISBOUND_TIMING_METADATA', journal_event_ordinal=ordinal)); continue
            identity = (timing['operation'], canonical(timing.get('identifier')))
            if identity in seen:
                flags.append(dict(code='DUPLICATE_OPERATION_IDENTIFIER_TIMING', journal_event_ordinal=ordinal)); continue
            seen.add(identity)
            calls.append(dict(operation=timing['operation'], identifier=timing.get('identifier'),
                wall_nanoseconds=timing['wall_nanoseconds'], process_CPU_nanoseconds=timing['process_CPU_nanoseconds'],
                returned=timing['returned'], error_type=timing.get('error_type'), matched_return_event=matched,
                journal_event_ordinal=ordinal, pending_list_index=index))
            if timing.get('error_type'): counts[('native_call_error_type',timing['error_type'])] += 1
    attempts = None if cache is None else cache.get('attempts')
    for index, attempt in enumerate(attempts if isinstance(attempts, list) else []):
        status = attempt.get('status'); counts[('optimizer_attempt_status', scalar(status))] += 1
        candidate = attempt.get('candidate') or attempt.get('raw_native_candidate')
        candidate = candidate if isinstance(candidate, dict) else {}
        code = candidate.get('optimizer_code'); stereo = candidate.get('stereo_valid')
        counts[('optimizer_code', scalar(code))] += 1; counts[('stereo_valid', scalar(stereo))] += 1
        issue = error(attempt.get('error'), '/attempts/' + str(index) + '/error')
        if issue: counts[('attempt_error_type', issue['code'])] += 1
        attempt_details.append(dict(candidate_id=attempt.get('candidate_id'), status=status,
            optimizer_code=code, stereo_valid=stereo, error=issue,
            source_pointer='/attempts/' + str(index)))
    d3_issues = []; issues_unavailable = 0
    for index, conformer in enumerate(packet.get('conformers', []) if packet is not None else []):
        issues = conformer.get('D3_issues')
        if not isinstance(issues, list): issues_unavailable += 1; continue
        for j, value in enumerate(issues):
            issue = error(value, '/conformers/' + str(index) + '/D3_issues/' + str(j))
            if issue:
                counts[('D3_issue_code', issue['code'])] += 1
                d3_issues.append(dict(conformer_id=conformer.get('conformer_id'), **issue))
    cache_error = error(cache.get('error'), '/error') if cache is not None else None
    if cache_error: counts[('cache_error_type', cache_error['code'])] += 1
    actual = saved['actual_conformers']; delivery_bin = 'UNKNOWN' if actual is None else str(actual)
    legacy = {}
    for field in ('worker_wall_seconds', 'worker_CPU_seconds', 'native_generation_wall_seconds'):
        value = manifest.get(field)
        legacy[field] = value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None
    current_reused = manifest.get('closed_cache_reused_without_UFF')
    row = dict(molecule_id=saved['molecule_id'], stream=source['stream'],
        producer_job_id=None if manifest.get('producer_job_id') is None else str(manifest['producer_job_id']),
        state=saved['state'], actual_conformers=actual, physical_delivered_rows=saved['delivered_conformers'],
        delivery_bin=delivery_bin, known_sparse_positive=actual in (1, 2),
        cache_available=cache is not None, cache_complete=None if cache is None else cache.get('complete'),
        closed_cache_reused_without_UFF=current_reused,
        embedding_calls_recorded_in_cache=None if cache is None else cache.get('embedding_calls'),
        optimizer_calls_recorded_in_cache=None if cache is None else cache.get('optimizer_calls'),
        embedded_candidates_recorded=None if cache is None or not isinstance(cache.get('embedded_candidate_ids'), list) else len(cache['embedded_candidate_ids']),
        optimizer_attempt_rows=None if not isinstance(attempts, list) else len(attempts),
        saved_valid_candidates=None if cache is None or not isinstance(cache.get('valid_candidates'), list) else len(cache['valid_candidates']),
        saved_canonical_candidates=None if cache is None or not isinstance(cache.get('canonical_candidates'), list) else len(cache['canonical_candidates']),
        cache_state=None if cache is None else cache.get('state'), cache_error=cache_error,
        attempt_details=attempt_details, d3_issues=d3_issues, D3_issues_metadata_unavailable_conformers=issues_unavailable,
        return_events_without_call_timing=dict(missing), journal_available=journal is not None,
        timing_metadata_flags=flags, timing_record_count=len(calls),
        category_counts=[dict(domain=domain,code=code,count=n) for (domain,code),n in sorted(counts.items())],
        legacy_clock_seconds=legacy)
    classes = []
    if actual is None: classes.append('UNKNOWN_DELIVERY_NOT_ZERO')
    elif actual == 0: classes.append('KNOWN_ZERO_DELIVERY')
    elif actual < 3: classes.append('KNOWN_SPARSE_POSITIVE_DELIVERY_NOT_FAILURE')
    if cache_error or d3_issues or any(a['status'] in ('NATIVE_FAILED','NATIVE_REJECTED') for a in attempt_details):
        classes.append('OBSERVED_CACHE_OPTIMIZER_OR_D3_DIAGNOSTICS')
    if any(call['returned'] is False for call in calls): classes.append('OBSERVED_NATIVE_CALL_EXCEPTION')
    if flags: classes.append('TIMING_METADATA_DIAGNOSTICS')
    row['record_classes'] = classes
    return dict(row=row, calls=calls, references={k:saved.get(k) for k in
        ('manifest_reference','cache_reference','packet_reference','events_reference')})


def evidence(result):
    """Original saved-evidence values survive unchanged; metadata has its own catalogs."""
    return {key:value for key,value in result.items() if key != METADATA_KEY}


class Accumulator:
    def __init__(self): self.groups = {}; self.molecules = 0; self.calls = 0

    def append(self, item):
        row = item['row']; stream = row['stream']; job = row['producer_job_id']; self.molecules += 1
        self.calls += len(item['calls'])
        keys = [('all',None,None),('stream',stream,None),('producer_job',None,job),('stream_producer_job',stream,job)]
        for key in keys:
            group = self.groups.setdefault(key, dict(n=0, delivery=Counter(), states=Counter(), categories=Counter(),
                count_fields={}, clocks={}, operations={}, missing=Counter(), reused=0, journal_missing=0,
                no_timing=0, timing_flags=0, physical=0))
            group['n'] += 1; group['delivery'][row['delivery_bin']] += 1; group['states'][row['state']] += 1
            group['physical'] += row['physical_delivered_rows']; group['reused'] += row['closed_cache_reused_without_UFF'] is True
            group['journal_missing'] += row['journal_available'] is False; group['no_timing'] += not item['calls']
            group['timing_flags'] += bool(row['timing_metadata_flags']); group['missing'].update(row['return_events_without_call_timing'])
            for cat in row['category_counts']: group['categories'][(cat['domain'],cat['code'])] += cat['count']
            for field in ('embedding_calls_recorded_in_cache','optimizer_calls_recorded_in_cache','embedded_candidates_recorded',
                          'optimizer_attempt_rows','saved_valid_candidates','saved_canonical_candidates'):
                observed = group['count_fields'].setdefault(field, [0,0])
                if row[field] is not None: observed[0] += 1; observed[1] += row[field]
            for field, value in row['legacy_clock_seconds'].items():
                observed = group['clocks'].setdefault(field, [0,Decimal(0)])
                if value is not None: observed[0] += 1; observed[1] += Decimal(str(value))
            touched = set()
            for call in item['calls']:
                op = call['operation']; touched.add(op)
                observed = group['operations'].setdefault(op, dict(calls=0,wall=0,cpu=0,returned=0,raised=0,unmatched=0,
                    delivered_known=0,delivery_unknown_molecules=0))
                observed['calls'] += 1; observed['wall'] += call['wall_nanoseconds']; observed['cpu'] += call['process_CPU_nanoseconds']
                observed['returned'] += call['returned'] is True; observed['raised'] += call['returned'] is False
                observed['unmatched'] += call['matched_return_event'] is False
            for op in touched:
                if row['actual_conformers'] is None: group['operations'][op]['delivery_unknown_molecules'] += 1
                else: group['operations'][op]['delivered_known'] += row['actual_conformers']

    def summaries(self):
        rows = []
        for (kind,stream,job),g in sorted(self.groups.items(), key=lambda x:canonical(x[0])):
            ops = {}
            for op in OPERATIONS:
                v = g['operations'].get(op)
                ops[op] = dict(measured_calls=0 if v is None else v['calls'],
                    wall_nanoseconds=None if v is None else v['wall'], process_CPU_nanoseconds=None if v is None else v['cpu'],
                    returned_calls=0 if v is None else v['returned'], raised_calls=0 if v is None else v['raised'],
                    measured_without_matching_return_event=0 if v is None else v['unmatched'],
                    return_events_without_timing=g['missing'][op],
                    known_actual_conformers_in_measured_call_molecules=0 if v is None else v['delivered_known'],
                    unknown_delivery_molecules_with_measured_calls=0 if v is None else v['delivery_unknown_molecules'])
            rows.append(dict(group_type=kind,stream=stream,producer_job_id=job,molecules=g['n'],
                delivery_molecules={key:g['delivery'][key] for key in ('0','1','2','3','UNKNOWN')},
                known_delivery_molecules=g['n']-g['delivery']['UNKNOWN'],
                known_actual_conformer_denominator=sum(int(key)*g['delivery'][key] for key in ('0','1','2','3')),
                physical_delivered_rows=g['physical'], known_sparse_positive_molecules=g['delivery']['1']+g['delivery']['2'],
                source_state_counts=dict(g['states']),cache_reused_molecules=g['reused'],
                journal_unavailable_molecules=g['journal_missing'],molecules_without_measured_call_timings=g['no_timing'],
                timing_metadata_diagnostic_molecules=g['timing_flags'],native_call_timings=ops,
                recorded_cache_counts={field:dict(observed_molecules=n,unavailable_molecules=g['n']-n,
                    sum_recorded_values=total if n else None) for field,(n,total) in g['count_fields'].items()},
                stored_worker_or_generation_clocks={field:dict(observed_molecules=n,unavailable_molecules=g['n']-n,
                    total_seconds_decimal=str(total) if n else None) for field,(n,total) in g['clocks'].items()},
                diagnostic_code_top20=[dict(domain=domain,code=code,count=n) for (domain,code),n in g['categories'].most_common(20)]))
        return rows


class Catalog:
    def __init__(self, root):
        import pyarrow as pa
        import pyarrow.parquet as pq
        self.pa = pa; self.pq = pq; self.root = Path(root); self.aggregate = Accumulator()
        self.paths = {name:self.root/('report_'+name+'.parquet') for name in ('molecules','native_calls','diagnostics')}
        base = [('molecule_id',pa.string()),('stream',pa.string()),('producer_job_id',pa.string())]
        self.schemas = dict(molecules=pa.schema(base+[('delivery_bin',pa.string()),('actual_conformers',pa.int64()),
            ('physical_delivered_rows',pa.int64()),('state',pa.string()),('metrics_json',pa.string())]),
            native_calls=pa.schema(base+[('operation',pa.string()),('identifier_json',pa.string()),('wall_nanoseconds',pa.int64()),
                ('process_CPU_nanoseconds',pa.int64()),('returned',pa.bool_()),('error_type',pa.string()),
                ('matched_return_event',pa.bool_()),('journal_event_ordinal',pa.int64()),('pending_list_index',pa.int64())]),
            diagnostics=pa.schema(base+[('delivery_bin',pa.string()),('record_classes_json',pa.string()),
                ('category_counts_json',pa.string()),('original_evidence_references_json',pa.string())]))
        self.writers = {name:pq.ParquetWriter(self.paths[name],schema,compression='zstd') for name,schema in self.schemas.items()}
        self.buffers = {name:[] for name in self.schemas}; self.rows = Counter(); self.done = False

    def flush(self, name):
        values = self.buffers[name]
        if values:
            self.writers[name].write_table(self.pa.Table.from_pylist(values,schema=self.schemas[name]))
            self.rows[name] += len(values); self.buffers[name] = []

    def append(self, result):
        item = result[METADATA_KEY]; row = item['row']; self.aggregate.append(item)
        base = {key:row[key] for key in ('molecule_id','stream','producer_job_id')}
        self.buffers['molecules'].append(dict(base,delivery_bin=row['delivery_bin'],actual_conformers=row['actual_conformers'],
            physical_delivered_rows=row['physical_delivered_rows'],state=row['state'],metrics_json=canonical(row)))
        for call in item['calls']:
            value = {key:val for key,val in call.items() if key != 'identifier'}
            self.buffers['native_calls'].append(dict(base,identifier_json=canonical(call['identifier']),**value))
        if row['record_classes']:
            self.buffers['diagnostics'].append(dict(base,delivery_bin=row['delivery_bin'],record_classes_json=canonical(row['record_classes']),
                category_counts_json=canonical(row['category_counts']),original_evidence_references_json=canonical(item['references'])))
        for name in self.buffers:
            if len(self.buffers[name]) >= 4096:self.flush(name)

    def close(self):
        if not self.done:
            for name in self.writers:self.flush(name); self.writers[name].close()
            self.done = True

    def finish(self, reference):
        self.close(); refs = {}
        for name,path in self.paths.items():
            actual = self.pq.ParquetFile(path).metadata.num_rows
            if actual != self.rows[name]:raise ValueError('REPORT_METRICS_PHYSICAL_ROW_CENSUS')
            refs[name] = dict(reference(path),rows=actual)
        categories = []
        for (kind,stream,job),g in self.aggregate.groups.items():
            categories.extend(dict(group_type=kind,stream=stream,producer_job_id=job,domain=domain,code=code,count=n)
                              for (domain,code),n in g['categories'].items())
        schema = self.pa.schema([('group_type',self.pa.string()),('stream',self.pa.string()),('producer_job_id',self.pa.string()),
            ('domain',self.pa.string()),('code',self.pa.string()),('count',self.pa.int64())])
        path = self.root/'report_diagnostic_code_counts.parquet'
        self.pq.write_table(self.pa.Table.from_pylist(categories,schema=schema),path,compression='zstd')
        refs['diagnostic_codes'] = dict(reference(path),rows=len(categories))
        return dict(schema='PUBCHEM_UFF3_FINAL_REPORT_METRICS_V1',status='COMPLETE_SAVED_METADATA_ONLY',
            molecules=self.aggregate.molecules,measured_native_calls=self.aggregate.calls,catalogs=refs,groups=self.aggregate.summaries(),
            unknown_delivery_not_converted_to_zero=True,sparse_delivery_not_classified_as_native_failure=True,
            internal_candidate_counts_not_delivered_conformer_counts=True,legacy_unmeasured_call_times_are_null=True,
            cache_counts_may_describe_prior_generation_when_reused=True,
            stored_native_generation_clock_may_predate_current_producer_when_reused=True,
            measured_call_clocks_exclude_journal_fsync=True,no_new_scientific_calls_or_per_MID_reads=True,
            original_error_text_in_pinned_cache_packet_and_journal=True)
