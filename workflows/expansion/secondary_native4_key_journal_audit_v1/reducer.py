"""JSON pair/mass/error-axis audit only: no RDKit or producer worker import."""
import collections,hashlib,json,re
KEY=re.compile(r'[A-Z]{14}-[A-Z]{10}-[A-Z]')
SIDS={'qm8_sdf','pdbbind_core','pdbbind_general','pdbbind_refined'}
AXES={'native_record','source_byte_verification','temporary_record_IO','native_SDF_graph'}
FLAGS=('boundary_complete','native_keys_present','source_variant_keys_present','union_present','has_unknown','native_errors','source_variant_errors','technical_error')


def need(value,message):
    if not value:raise ValueError(message)


def canonical(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'),sort_keys=True,allow_nan=False).encode()


def pairs_unique(items):
    result={}
    for k,v in items:need(k not in result,'DUPLICATE_JSON_FIELD');result[k]=v
    return result


def source_key(row):
    sid=row['source_id'];ordinal=row['source_format_ordinal']
    need(sid in SIDS and type(ordinal) is int and ordinal>=0 and row['format']=='SDF','EXACT_SELECTED_ORIGINAL_PHYSICAL_SDF_IDENTITY')
    need(type(row['complete_record_boundary']) is bool and type(row['raw_record_bytes']) is int and row['raw_record_bytes']>0
        and isinstance(row['raw_record_sha256'],str) and re.fullmatch('[0-9a-f]{64}',row['raw_record_sha256']),'SOURCE_RECORD_FRAME_AND_ORIGINAL_FLAG')
    return sid,ordinal


def key_set(values):
    need(isinstance(values,list) and all(isinstance(k,str) and KEY.fullmatch(k) for k in values),'RECORDED_FULL_KEY_TOKEN_SCHEMA_ONLY')
    need(values==sorted(set(values)),'RECORDED_KEYS_SORTED_UNIQUE');return set(values)


def cause(axis,error):
    if axis=='native_record' and 'SOURCE_RECORD_BOUNDARY_UNKNOWN_NOT_REPAIRED' in error:return 'NATIVE_RECORD_BOUNDARY_FLAG_FALSE'
    if axis=='source_byte_verification':return 'SOURCE_BYTE_VERIFICATION_PHASE_ERROR'
    if axis=='temporary_record_IO':return 'TEMPORARY_RECORD_IO_PHASE_ERROR'
    if axis=='native_SDF_graph':
        for token,label in (('EXACT_SINGLE_ORIGINAL_RECORD','SUPPLIER_RECORDED_COUNT_NOT_ONE'),('SOURCE_SDF_PARSER_NONE_UNKNOWN','SUPPLIER_RECORDED_NONE_NO_SUBCAUSE'),
            ('SOURCE_NATIVE_GRAPH_KEY_UNKNOWN','NATIVE_KEY_OUTPUT_MISSING_OR_INVALID')):
            if token in error:return label
        return 'NATIVE_SUBPHASE_UNKNOWN_INCLUDES_SUPPLIER_OR_TEMP_CLEANUP'
    return 'UNRECORDED_PHASE_OR_CAUSE_UNKNOWN'


def recorded_type(message):
    structured=message.get('original_error',{})
    value=structured.get('exception_type') if isinstance(structured,dict) else None
    if isinstance(value,str) and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}',value):return value
    text=message.get('error');m=re.match(r'^([A-Za-z_][A-Za-z0-9_]{0,127})(?::|\()',text) if isinstance(text,str) else None
    return m[1] if m else 'NO_EXCEPTION_TYPE_RECORDED'


def axes(value):
    row=value['source'];boundary=row['complete_record_boundary'];causes=set();messages=[];issues=[]
    technical='technical_error' in value
    if technical:
        native=set();variants=set();native_errors=[];variant_errors=[]
        need(value['observed_full_key_union']==value['WP5_key_union']==[] and value['has_unknown'] is True,'ORIGINAL_FUTURE_TECHNICAL_UNKNOWN_SCHEMA')
        causes.add(('technical','FUTURE_OR_RESULT_VALIDATION_TECHNICAL_ERROR'));messages.append({'axis':'technical','error':value['technical_error']})
    else:
        native=key_set(value['native_SDF_full_keys']);variants=set();native_errors=value['native_graph_errors'];variant_errors=[]
        need(isinstance(native_errors,list) and isinstance(value['variant_observations'],list),'RECORDED_NATIVE_AND_SOURCE_VARIANT_ERROR_AXES')
        for e in native_errors:
            need(isinstance(e['axis'],str) and isinstance(e['error'],str),'ORIGINAL_NATIVE_ERROR_TEXT_ONLY')
            axis=e['axis'] if e['axis'] in AXES else 'UNRECORDED_NATIVE_AXIS'
            causes.add((axis,cause(axis,e['error'])));messages.append(e)
        for v in value['variant_observations']:
            variants.update(key_set(v['full_keys']));need(isinstance(v['errors'],list),'ORIGINAL_VARIANT_ERRORS_LIST')
            for e in v['errors']:
                variant_errors.append(e);text=str(e.get('error',e.get('message','')))
                label='PRESENT_SOURCE_VARIANT_EMPTY_OR_INVALID_UTF8' if text=='ORIGINAL_PRESENT_SMILES_EMPTY_OR_INVALID_UTF8_UNKNOWN' else 'SOURCE_VARIANT_KEY_UNRESOLVED_SUBPHASE_UNKNOWN'
                causes.add(('source_variant',label));messages.append({'axis':'source_variant','field':v['field'],'variant':v['variant'],'original_error':e})
        if bool(native_errors or variant_errors)!=value['has_unknown']:issues.append('HAS_UNKNOWN_DOES_NOT_MATCH_RECORDED_ERROR_AXES')
        boundary_errors=[e for e in native_errors if e['axis']=='native_record' and e['error']=='SOURCE_RECORD_BOUNDARY_UNKNOWN_NOT_REPAIRED']
        if (not boundary)!=bool(boundary_errors):issues.append('BOUNDARY_FLAG_AND_EXPLICIT_BOUNDARY_ERROR_DISAGREE')
    union=key_set(value['observed_full_key_union'])
    if native|variants!=union:issues.append('NATIVE_AND_PRESENT_SOURCE_KEY_UNION_DISAGREES_WITH_RECORDED_UNION')
    table_error=row.get('native_table_error')
    if table_error is not None:
        causes.add(('source_native_table','SOURCE_NATIVE_TABLE_ERROR_NOT_GRAPH_FAILURE_PROOF'));messages.append({'axis':'source_native_table','error':table_error})
    if issues:causes.add(('contract','RECORDED_RESULT_CONTRACT_ISSUE_REQUIRES_HOLD'))
    flags=(boundary,bool(native),bool(variants),bool(union),value['has_unknown'],bool(native_errors),bool(variant_errors),technical)
    need(all(type(v) is bool for v in flags),'RECORDED_FLAG_TYPES')
    relation='NEITHER' if not native and not variants else 'NATIVE_ONLY' if native and not variants else 'SOURCE_VARIANT_ONLY' if variants and not native else 'BOTH_EQUAL' if native==variants else 'BOTH_DIFFER_OVERLAP' if native&variants else 'BOTH_DISJOINT'
    return {'causes':sorted(causes),'messages':messages,'issues':issues,'flags':''.join('1' if v else '0' for v in flags),'key_axis_relation':relation,
        'native_keys_present':bool(native),'source_variant_keys_present':bool(variants),'union_present':bool(union),'has_unknown':value['has_unknown'],
        'source_variant_count':0 if technical else len(value['variant_observations']),'native_table_available':row.get('native_non_H_composition_evidence') is not None,
        'boundary_false_is_proven_parser_failure':False,'native_failure_subcause_or_cleanup':'UNKNOWN_UNLESS_RECORDED_EXPLICIT_TOKEN',
        'record_ordinal_bin':'FIRST_RECORD' if row.get('record_ordinal')==0 else 'LATER_RECORD',
        'raw_record_byte_bin':'LE64' if row['raw_record_bytes']<=64 else 'GT64',
        'native_title_state':row.get('native_title',{}).get('state') if row.get('native_title',{}).get('state') in
            {'MISSING','EMPTY_PRESERVED','LITERAL_UTF8','INVALID_UTF8_UNKNOWN'} else 'NOT_RECORDED'}


class Reducer:
    def __init__(self,expected,populations,max_pending=32):
        self.expected=dict(expected);self.populations=dict(populations);self.max_pending=max_pending;self.pending={};self.seen=set();self.done=set()
        self.sources=collections.Counter();self.results=collections.Counter();self.unknown=collections.Counter();self.any_key=collections.Counter()
        self.cross=collections.Counter();self.relations=collections.Counter();self.causes=collections.Counter();self.issues=collections.Counter()
        self.variant_count=collections.Counter();self.table=collections.Counter();self.boundary_hints=collections.Counter();self.messages=collections.Counter()
        self.error_types=collections.Counter()
        self.lines=0;self.peak_pending=0

    def feed(self,value,locator):
        self.lines+=1;kind=value['event']
        if kind=='SOURCE_DURABLE_BEFORE_KEY_DISPATCH':
            row=value['source'];key=source_key(row);sid,ordinal=key
            need(sid in self.expected and ordinal<self.populations[sid] and key not in self.seen,'SOURCE_SELECTION_DUPLICATE_OR_OUTSIDE_ACTUAL_POPULATION')
            self.seen.add(key);self.sources[sid]+=1;self.pending[key]=(row,locator)
            need(len(self.pending)<=self.max_pending,'RECORDED_MORE_THAN32_OUTSTANDING_PAIRS');self.peak_pending=max(self.peak_pending,len(self.pending));return None
        need(kind=='RESULT_DURABLE_BEFORE_INDEX_OR_UNION','ONLY_ORIGINAL_SOURCE_AND_RESULT_EVENT_TYPES');result=value['result'];row=result['source'];key=source_key(row);sid,ordinal=key
        need(key in self.pending and key not in self.done,'RESULT_BEFORE_SOURCE_OR_DUPLICATE_RESULT');source,source_locator=self.pending.pop(key)
        need(source==row,'LITERAL_SOURCE_RESULT_PAIR_CONFLICT');self.done.add(key);audit=axes(result);self.results[sid]+=1
        self.unknown[sid]+=audit['has_unknown'];self.any_key[sid]+=audit['union_present'];self.cross[(sid,audit['flags'])]+=1
        self.relations[(sid,audit['key_axis_relation'])]+=1;self.variant_count[(sid,str(audit['source_variant_count']))]+=1;self.table[(sid,audit['native_table_available'])]+=1
        self.boundary_hints[(sid,row['complete_record_boundary'],audit['record_ordinal_bin'],audit['raw_record_byte_bin'],audit['native_title_state'])]+=1
        for axis,label in audit['causes']:self.causes[(sid,axis,label)]+=1
        for issue in audit['issues']:self.issues[(sid,issue)]+=1
        for message in audit['messages']:
            axis=message['axis'] if message['axis'] in AXES|{'technical','source_variant','source_native_table'} else 'UNRECORDED_AXIS'
            self.messages[(sid,axis,hashlib.sha256(canonical(message)).hexdigest())]+=1
            self.error_types[(sid,axis,recorded_type(message))]+=1
        return {'key':key,'source':source,'result':result,'source_event_locator':source_locator,'result_event_locator':locator,'audit':audit}

    def finish(self):
        need(not self.pending and dict(self.sources)==dict(self.results)==self.expected and len(self.seen)==len(self.done)==sum(self.expected.values())
            and self.lines==2*sum(self.expected.values()),'ALL_SELECTED_SOURCE_RESULT_MASS_AND_EOF_CONSERVATION')
        return self.summary()

    def summary(self):
        return {'events_seen':self.lines,'source_counts':dict(self.sources),'result_counts':dict(self.results),'has_unknown_counts':dict(self.unknown),
            'any_observed_key_union_counts':dict(self.any_key),'peak_pending_pairs':self.peak_pending,'remaining_unpaired':len(self.pending),
            'cross_axis_flag_order':list(FLAGS),'cross_axis_counts':[{'source_id':s,'flags':f,'count':n} for (s,f),n in sorted(self.cross.items())],
            'native_vs_source_variant_key_relations':[{'source_id':s,'relation':r,'count':n} for (s,r),n in sorted(self.relations.items())],
            'cause_counts':[{'source_id':s,'axis':a,'recorded_cause_class':c,'count':n} for (s,a,c),n in sorted(self.causes.items())],
            'recorded_exception_type_counts':[{'source_id':s,'axis':a,'recorded_type_or_prefix':t,'count':n} for (s,a,t),n in sorted(self.error_types.items())],
            'contract_issues':[{'source_id':s,'issue':i,'count':n} for (s,i),n in sorted(self.issues.items())],
            'declared_source_variant_count_histogram':[{'source_id':s,'present_declared_variants':v,'count':n} for (s,v),n in sorted(self.variant_count.items())],
            'native_table_composition_evidence_counts':[{'source_id':s,'available':v,'count':n} for (s,v),n in sorted(self.table.items())],
            'boundary_candidate_metadata_only_counts':[{'source_id':s,'complete_record_boundary':b,'record_ordinal_bin':r,'bytes_bin':z,'native_title_state':t,'count':n}
                for (s,b,r,z,t),n in sorted(self.boundary_hints.items())],
            'unique_error_message_digests':len(self.messages),'error_messages_or_SMILES_exposed_in_summary':False,
            'EOF_missing_delimiter_is_actual_cause':'UNKNOWN_NOT_TESTED','high_unknown_is_original_graph_unavailable':False,'profile_scientific_acceptance':False}
