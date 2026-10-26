"""Bounded technical report publication and small receipts; no scientific decisions."""
from __future__ import annotations
import hashlib,json,os,pathlib,traceback
from precision import need
from relocation import actual_ref

SMALL_CAP=262144


def encode(value):
    return (json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()


def brief(value,limit=1600):
    text=str(value)
    return {'text':text[:limit],'original_characters':len(text),'shortened':len(text)>limit}


def error_rows(values,maximum=16):
    rows=[]
    for row in values[:maximum]:
        rows.append({key:brief(row[key],1600 if key=='error' else 400) for key in
            ('stage','error','traceback','test_id','reason','result') if key in row})
    return {'count':len(values),'short_list':rows,'omitted_from_small_receipt':max(0,len(values)-maximum),
        'complete_details_location':'full report when successfully written'}


def small_diagnosis(report):
    tests=report['synthetic_test_receipt'];failures=report['failures'];classifications={};by_field={};rows=[]
    for item in failures:
        category=item['diagnosis_status'];field=item['field']
        classifications[category]=classifications.get(category,0)+1
        by_field.setdefault(field,{})[category]=by_field.setdefault(field,{}).get(category,0)+1
        components=item.get('componentwise_native_print_checks',[])
        row={'original_failure':item['original_failure'],'field':field,'classification':category,
            'original_failure_retained':item['original_failure_retained'],
            'original_frozen_check_reproduced':item.get('original_frozen_check_reproduced'),
            'both_actual_input_bindings_and_targets_verified':item.get('both_actual_input_bindings_and_targets_verified'),
            'all_components_within_native_print_propagation_only':item.get('all_components_within_native_print_propagation_only'),
            'still_unexplained_under_native_print_hypothesis':item['still_unexplained_under_native_print_hypothesis'],
            'component_count':len(components),
            'native_centers_within_print_bound_count':sum(v['native_centers_within_print_bound'] is True for v in components),
            'parser_centers_within_print_bound_count':sum(v['parser_float_centers_within_print_bound'] is True for v in components)}
        if 'diagnostic_error' in item:row['diagnostic_error']=brief(item['diagnostic_error'])
        orbit=item.get('geometry_orbit')
        row['same_geometry_orbit_within_predeclared_coordinate_atol']=orbit.get('same_geometry_orbit_within_predeclared_coordinate_atol') if isinstance(orbit,dict) else None
        rows.append(row)
    return {'schema':'PPRIME_NATIVE72_ALPHA_SMALL_DIAGNOSIS_RECEIPT_V2','runtime':report['runtime'],
        'diagnosis_status':report['status'],'all72_inputs_closed':report['all72_inputs_closed'],
        'actual_cases_read':report['actual_cases_read'],'raw_dispatch_gate':report['raw_dispatch_gate'],
        'four_fixtures_actual':{'status':tests['status'],'tests_required':tests['tests_required'],
            'tests_run':tests['tests_run'],'successful_test_count':len(tests['successful_test_ids']),
            'successful_test_ids':tests['successful_test_ids'][:4],
            'failure_count':len(tests['failures']),'error_count':len(tests['errors']),
            'failures':error_rows(tests['failures'],4),'errors':error_rows(tests['errors'],4),
            'skipped_count':len(tests['skipped']),'expected_failure_count':len(tests['expected_failures']),
            'unexpected_success_count':len(tests['unexpected_successes']),'source':tests['source']},
        'original_failure_count':len(report['original_failures']),
        'original_15_failures_unchanged':len(report['original_failures'])==15 and len(failures)==15
            and all(item['original_failure_retained'] is True for item in failures)
            and [item['original_failure'] for item in failures]==report['original_failures'],
        'original_field_failure_counts':report['original_field_failure_counts'],
        'classification_counts':classifications,'classification_counts_by_field':by_field,
        'per_original_failure_classification_and_key_judgments':rows,
        'case_read_errors':error_rows(report['case_read_errors']),
        'metadata_preflight_status':report['retained72_metadata_preflight']['status'],
        'metadata_preflight_errors':error_rows(report['retained72_metadata_preflight']['errors']),
        'input_checks_count':len(report['input_checks']),
        'actual_input_bindings_and_target_verified_count':sum(row['all_actual_input_bindings_and_target_verified'] is True for row in report['input_checks']),
        'soft_stop_new_reads':report['soft_stop_new_reads'],
        'original_all_predeclared_vector_tolerances':report['original_all_predeclared_vector_tolerances'],
        'printed_halfwidth_is_diagnostic_hypothesis_only':report['printed_halfwidth_is_diagnostic_hypothesis_only'],
        'original_rounding_and_numeric_criteria_revised':False,'SCF_failure_or_cause_inferred':False,
        'automatic_PASS_or_QM_release':False,'QM_or_UFF_calls':0,
        'actual_alpha_database_observation_reference':report['actual_alpha_database_observation_reference'],
        'actual_terminal_sacct_cost_closure_required':True,
        'source_report_is_not_a_quality_gate_revision':True}


def write_small(path,value):
    raw=encode(value);need(len(raw)<=SMALL_CAP,'SMALL_DIAGNOSIS_RECEIPT_EXCEEDS256K_NO_TRUNCATION')
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    observed=actual_ref(path)
    need(observed['bytes']==len(raw) and observed['sha256']==hashlib.sha256(raw).hexdigest(),'SMALL_RECEIPT_READBACK_DIFFERS')
    return observed


def publish_report(report,output,*,maximum_report_bytes,whole_output_cap_bytes):
    """A write/serialization failure still attempts an explicit bounded failure receipt."""
    output=pathlib.Path(output);raw=None;intended=None;observed=None;readback_confirmed=False;summary=None
    try:
        raw=encode(report);intended={'path':str(output),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        summary=small_diagnosis(report)
        need(len(raw)<=maximum_report_bytes,'BOUNDED_DIAGNOSTIC_REPORT_EXCEEDS32M_NO_TRUNCATION_OR_FAKE_PASS')
        output.parent.mkdir(parents=True,exist_ok=True)
        existing=sum(path.stat().st_size for path in output.parent.rglob('*') if path.is_file())
        need(existing+len(raw)+2*SMALL_CAP<=whole_output_cap_bytes,'WHOLE64M_OUTPUT_CAP_MUST_RESERVE_REPORT_AND_SMALL_RECEIPTS')
        with output.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        observed=actual_ref(output);need(observed==intended,'FULL_REPORT_READBACK_BYTES_OR_SHA_DIFFERS')
        readback_confirmed=True
        summary.update(status='FULL_REPORT_AND_SMALL_SUMMARY_WRITTEN',actual_serialized_bytes=len(raw),
            full_report_bytes=observed['bytes'],full_report_sha256=observed['sha256'],full_report_reference=observed,
            maximum_report_bytes=maximum_report_bytes,whole_output_cap_bytes=whole_output_cap_bytes,
            report_capacity_is_technical_not_scientific_threshold=True)
        receipt=write_small(output.parent/'diagnosis_summary.json',summary)
        return {'status':'FULL_REPORT_AND_SMALL_SUMMARY_WRITTEN','report':observed,'summary':receipt,
            'original_failure_count':15,'QM_calls':0,'all72_inputs_closed':report['all72_inputs_closed']}
    except Exception as exc:
        detail={'stage':'serialize_or_write_report_or_summary','error':brief(type(exc).__name__+': '+str(exc),2400),
            'traceback':brief(traceback.format_exc(),6000)}
        if summary is None:
            # Preserve essential actual state even if compact metadata construction fails.
            tests=report.get('synthetic_test_receipt',{})
            summary={'schema':'PPRIME_NATIVE72_ALPHA_SMALL_DIAGNOSIS_RECEIPT_V2','runtime':report.get('runtime'),
                'all72_inputs_closed':report.get('all72_inputs_closed'),'actual_cases_read':report.get('actual_cases_read'),
                'four_fixtures_actual':{'status':tests.get('status'),'tests_required':tests.get('tests_required'),
                    'tests_run':tests.get('tests_run'),'successful_test_count':len(tests.get('successful_test_ids',[])),
                    'failure_count':len(tests.get('failures',[])),'error_count':len(tests.get('errors',[])),
                    'failures':error_rows(tests.get('failures',[]),4),'errors':error_rows(tests.get('errors',[]),4)},
                'case_read_errors':error_rows(report.get('case_read_errors',[])),
                'original_failure_count':len(report.get('original_failures',[])),
                'original_15_failures_unchanged':None,'original_failure_preservation_not_recomputed':True}
        summary.update(status='REPORT_OR_SUMMARY_PUBLICATION_FAILED',publication_error=detail,
            actual_serialized_bytes=len(raw) if raw is not None else None,
            serialization_completed=raw is not None,intended_full_report_reference=intended,
            full_report_reference_after_successful_readback=observed if readback_confirmed else None,
            observed_full_report_reference_even_if_readback_mismatch=observed,
            maximum_report_bytes=maximum_report_bytes,whole_output_cap_bytes=whole_output_cap_bytes,
            report_capacity_is_technical_not_scientific_threshold=True)
        try:
            summary['partial_or_existing_report_stat_only']={'path':str(output),'exists':output.exists(),
                'bytes':output.stat().st_size if output.exists() else None,
                'SHA_not_inferred_from_intended_bytes':True}
            output.parent.mkdir(parents=True,exist_ok=True)
            receipt=write_small(output.parent/'report_write_failure.json',summary)
            return {'status':'REPORT_OR_SUMMARY_PUBLICATION_FAILED','failure_receipt':receipt,
                'actual_serialized_bytes':summary['actual_serialized_bytes'],
                'all72_inputs_closed':report.get('all72_inputs_closed'),'publication_error':detail}
        except Exception as receipt_exc:
            return {'status':'REPORT_AND_FAILURE_RECEIPT_PUBLICATION_FAILED',
                'actual_serialized_bytes':summary['actual_serialized_bytes'],
                'intended_full_report_reference':intended,'all72_inputs_closed':report.get('all72_inputs_closed'),
                'actual_cases_read':report.get('actual_cases_read'),'four_fixtures_actual':summary.get('four_fixtures_actual'),
                'case_read_errors':summary.get('case_read_errors'),'classification_counts':summary.get('classification_counts'),
                'publication_error':detail,'failure_receipt_error':brief(type(receipt_exc).__name__+': '+str(receipt_exc))}
