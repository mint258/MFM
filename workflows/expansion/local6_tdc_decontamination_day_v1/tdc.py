"""Original source-before-result envelope joins; accepted exact2 is composition only."""
import collections,hashlib
from . import contract as C,io as I,projection as P

def accepted_two(authority,check):
    sources={};observations={};member='admet_group/solubility_aqsoldb/test.csv'
    for event,location in I.rows(authority['TDC2_DATA_reference'],check):
        if event['event']=='ROW_DURABLE_BEFORE_SUBMIT':
            s=event['source'];ordinal=s['source_row_ordinal'];C.need(ordinal in (1159,1160) and ordinal not in sources,'EXACT_TWO_ALPHA_SOURCE_EVENTS')
            sources[ordinal]=(s,location)
        else:
            C.need(event['event']=='RESULT_DURABLE_BEFORE_PARQUET_OR_AGGREGATION','ORIGINAL_ALPHA_RESULT_ENVELOPE')
            value=event['value']['observation'];s=value['source'];ordinal=s['source_row_ordinal']
            C.need(ordinal in sources and ordinal not in observations and I.equal_json(s,sources[ordinal][0]),'ALPHA_SOURCE_DURABLE_BEFORE_EXACT_RESULT')
            original=s['original_source'];result=s['original_result'];atoms=value['atoms_only_evidence']
            C.need(P.source_key(original)==(member,ordinal) and I.equal_json(result['source'],original)
                and result['identity_state']=='ORIGINAL_SMILES_UNRESOLVED' and value['key_state']=='ORIGINAL_SMILES_UNRESOLVED'
                and value['SMILES_derived_full_keys']==value['WP5_keys']==[] and value['original_result_unchanged'] is True
                and value['graph_charge_stereo_and_original_cause']=='UNKNOWN'
                and atoms['state']=='SOURCE_SMILES_EXPLICIT_ATOMS_OBSERVED_NOT_GRAPH_IDENTITY','UNCHANGED_GRAPH_UNKNOWN_ATOMS_ONLY_EVIDENCE')
            C.need(type(s['source_record_bytes'])is int and s['source_record_bytes']>0 and type(s['source_record_sha256'])is str
                and len(s['source_record_sha256'])==64,'ORIGINAL_SOURCE_FIELD_DIGEST_LOCATOR_NOT_RESERIALIZED_ALPHA_KEY_ORDER')
            approved=next(v for v in authority['TDC2_accepted_observations'] if v['physical_record_ordinal']==ordinal)
            C.need(atoms['composition']==approved['composition'] and approved['graph_charge_stereo_and_original_cause']=='UNKNOWN'
                and approved['full_keys']==[],'MATCH_ROOT_ACCEPTED_COMPOSITION_NO_NEW_PARSER_CALL')
            observations[ordinal]={'original_source':original,'original_result':result,'composition':atoms['composition'],
                'original_source_record_bytes':s['source_record_bytes'],'original_source_record_sha256':s['source_record_sha256'],
                'Alpha_source_location':sources[ordinal][1],'Alpha_result_location':location,
                'origin_alpha_reference':authority['TDC2_origin_DATA_reference'],'new_graph_SUCCESS':False}
    C.need(set(sources)==set(observations)=={1159,1160},'ALL_TWO_PAIRS_WHOLE_EOF_SHA_NOT_PREFIX')
    return {(member,n):v for n,v in observations.items()}

def bind_main_source(accepted,source,result):
    # Alpha's journal canonicalizer may reorder nested dict keys. The original
    # source-field digest was made before that serialization; replay its exact
    # ordering from the Main producer, not from the sorted Alpha representation.
    C.need(I.equal_json(accepted['original_source'],source) and I.equal_json(accepted['original_result'],result),'EXACT_MAIN_SOURCE_AND_RESULT_NOT_ALPHA_DICT_ORDER')
    b=I.dump(source);C.need(len(b)==accepted['original_source_record_bytes']
        and hashlib.sha256(b).hexdigest()==accepted['original_source_record_sha256'],'ORIGINAL_MAIN_SOURCE_FIELD_BYTES_MATCH_ALPHA_PRODUCER_DIGEST')

def run(authority,out,budget):
    out.mkdir(parents=True,mode=0o700);accepted=accepted_two(authority,budget.check);pending={};next_ordinal=collections.Counter();source_counts=collections.Counter();result_counts=collections.Counter()
    states=collections.Counter();roles=collections.Counter();subdatasets=collections.Counter();used=set();peak=0
    writer=I.Lines(out/'tdc_admet.strict5.jsonl',budget);lineage=I.Lines(out/'tdc_original_lineage.DATA.jsonl',budget)
    known=unknown=0;archive=authority['TDC_original_archive_reference']
    try:
        for event,location in I.rows(authority['TDC_journal_reference'],budget.check):
            kind=event['event']
            if kind=='SOURCE_ROW_DURABLE_BEFORE_WORKER_DISPATCH':
                source=event['source'];key=P.source_key(source);name,ordinal=key
                C.need(name in authority['TDC_member_counts'] and ordinal==next_ordinal[name] and key not in pending,'ORIGINAL_MEMBER_PHYSICAL_ORDER_NO_DUPLICATE_SOURCE')
                next_ordinal[name]+=1;source_counts[name]+=1;pending[key]=(source,location);peak=max(peak,len(pending));C.need(peak<=32,'ORIGINAL32_PENDING_ENVELOPE_BOUND')
            else:
                C.need(kind=='ORIGINAL_ROW_IDENTITY_RESULT_COMPLETE','ORIGINAL_MAIN_JOURNAL_ENVELOPE')
                result=event['worker_observation']['result'];source=result['source'];key=P.source_key(source)
                C.need(key in pending and I.equal_json(pending[key][0],source),'RESULT_MATCHES_EXACT_PRIOR_SOURCE_NOT_COMPLETION_ORDER')
                original,source_location=pending.pop(key);fallback=accepted.get(key) if result['identity_state']!='FULL_KEYS_DERIVED' else None
                if fallback is not None:bind_main_source(fallback,source,result)
                row=P.tdc(source,result,archive['sha256'],fallback);writer.append(row)
                if fallback is None:known+=1
                else:C.need(key not in used,'EACH_ACCEPTED_UNKNOWN_USED_ONCE');used.add(key);unknown+=1
                states[result['identity_state']]+=1;roles[row['role']]+=1;subdatasets[row['subdataset']]+=1;result_counts[key[0]]+=1
                lineage.append({'strict_source_id':row['source_id'],'member_name':key[0],'physical_record_ordinal':key[1],
                    'original_native_Drug_ID':source['original_Drug_ID'],'original_split':source['original_split'],
                    'original_identity_state':result['identity_state'],'original_identity_errors':result.get('identity_errors'),
                    'original_source_event_location':source_location,'original_result_event_location':location,
                    'conservative_composition_policy_applied':fallback is not None,'accepted_Alpha_evidence':fallback,
                    'original_graph_charge_stereo_and_cause_for_two':'UNKNOWN' if fallback is not None else 'UNCHANGED_SOURCE_OBSERVATION',
                    'source_SMILES_reparsed_or_graph_key_recomputed':False,'assay_Y_decoded':False})
        C.need(not pending and dict(source_counts)==dict(result_counts)==authority['TDC_member_counts']
            and known==81807 and unknown==2 and used==set(accepted),'ALL81809_44_MEMBERS_AND_EXACT_TWO_COMPLETION')
        C.need(len(subdatasets)==22 and set(roles)=={'train_val','test'},'ALL_ORIGINAL22_ENDPOINTS_AND_BOTH_SOURCE_SPLITS')
        ref=writer.close();audit=lineage.close();read=I.readback(ref,list(roles),list(subdatasets),budget.check)
        C.need(ref['rows']==81809,'FULL_TDC_ROWS_NOT_TEST_ONLY')
        return {'dataset':'tdc_admet','identities':ref,'records':81809,'original_physical_rows':81809,'unresolved_without_identity_or_composition':0,
            'original_graph_UNKNOWN_rows_preserved':2,'known_original_key_rows':81807,'accepted_conservative_composition_rows':2,
            'role_counts':dict(roles),'required_roles':sorted(roles),'required_subdatasets':sorted(subdatasets),'readback':read,
            'raw_artifacts':[authority['TDC_journal_reference'],authority['TDC2_DATA_reference']],
            'origin_raw_artifacts':[archive,authority['TDC2_origin_DATA_reference']],'source_before_result_peak_pending':peak,
            'lineage_DATA_reference':audit,'new_MolFromSmiles_InChIKey_UFF_QM_calls':0}
    finally:writer.close();lineage.close()
