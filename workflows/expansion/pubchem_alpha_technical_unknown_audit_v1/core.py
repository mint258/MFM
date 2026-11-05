"""Classify recorded evidence only; no chemistry or recoverability inference."""
import collections
import json
import re

COUNTS = {'accepted': 110046364, 'chemReject': 14764875, 'technicalUnresolved': 46201}
FIELDS = ('category', 'ordinal', 'cid_source_ascii', 'source_smiles', 'source_smiles_sha256',
          'source_part_reference_json', 'technical_codes', 'legacy_reasons', 'audit_parse_succeeded',
          'audit_flags_json', 'audit_X01', 'audit_X02', 'audit_X03', 'audit_X04', 'audit_X05',
          'full_dispatcher_result_json', 'error_evidence_json')
FRAME = re.compile(r'File "([^"]+)", line (\d+), in ([^\n]+)')


def classify(row):
    errors = json.loads(row['error_evidence_json'])
    if not isinstance(errors, dict):
        raise ValueError('Original error evidence must be an object')
    entries = []
    for stage, value in sorted(errors.items()):
        if not isinstance(value, dict):
            raise ValueError('Original stage error evidence must be an object')
        trace = value.get('traceback')
        frames = [dict(path=p, line=int(n), function=f.strip()) for p, n, f in FRAME.findall(trace or '')]
        generic = any(f['path'].replace('\\', '/').endswith('/Scaffolds/MurckoScaffold.py')
                      and f['function'] == 'MakeScaffoldGeneric' for f in frames)
        remove_hs_text = bool(trace and re.search(r'\b(?:Chem\.)?RemoveHs\s*\(', trace))
        entries.append(dict(stage=stage, exception_type=value.get('type'), message=value.get('message'),
            traceback_present=isinstance(trace, str) and bool(trace), traceback_frames=frames,
            official_generic_scaffold_frame_recorded=generic,
            RemoveHs_call_text_recorded=remove_hs_text,
            generic_RemoveHs_AtomValence_trace_candidate=(generic and remove_hs_text
                and value.get('type') == 'AtomValenceException'),
            observed_evidence_only=True, recoverable_by_representation_repair=None))
    return dict(errors=entries, original_error_stages=sorted(errors),
        no_recorded_exception=not entries,
        generic_RemoveHs_AtomValence_trace_candidate=any(e['generic_RemoveHs_AtomValence_trace_candidate'] for e in entries),
        chemical_parse_or_feature_retried=False, P5_to_C5_cause_inferred=False,
        original_UNKNOWN_retained=True)


def add_counts(counter, row, observation):
    counter['rows'] += 1
    counter['rows/no_recorded_exception'] += int(observation['no_recorded_exception'])
    counter['rows/generic_RemoveHs_AtomValence_trace_candidate'] += int(observation['generic_RemoveHs_AtomValence_trace_candidate'])
    counter['audit_parse/'+str(row['audit_parse_succeeded'])] += 1
    flags = {k:row[k] for k in ('audit_X01','audit_X02','audit_X03','audit_X04','audit_X05')}
    counter['rows/all_X_false'] += int(row['audit_parse_succeeded'] is True and all(v is False for v in flags.values()))
    for code in row['technical_codes'] or []:counter['technical_code/'+code] += 1
    for reason in row['legacy_reasons'] or []:counter['legacy_reason/'+reason] += 1
    for error in observation['errors']:
        counter['exception_stage/'+error['stage']] += 1
        counter['exception_type/'+str(error['exception_type'])] += 1
        signature = json.dumps([error['stage'],error['exception_type'],error['message']],ensure_ascii=True,separators=(',',':'))
        counter['exact_exception_signature/'+signature] += 1
        for f in error['traceback_frames']:
            counter['traceback_site/'+json.dumps([f['path'],f['line'],f['function']],separators=(',',':'))] += 1


def category_counts(values):
    result = collections.Counter(values)
    if not set(result) <= set(COUNTS):raise ValueError('Unknown/null source category')
    return {key:result[key] for key in COUNTS}
