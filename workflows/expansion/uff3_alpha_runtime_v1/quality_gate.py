"""Taskbook strict >1% anomalous NEW record masks: stop and report user."""
import json


def require_within_one_percent(qa):
    rows=qa['all_stream_field_counts'];seen=set();stops=[]
    if not isinstance(rows,list)or not rows:raise RuntimeError('ACTUAL_CANONICAL_RECORD_MASK_COUNTS_REQUIRED')
    for row in rows:
        field=str(row['field_id']);n=row['canonical_records'];masked=row['newly_masked_records']
        if field in seen or type(n)is not int or type(masked)is not int or not 0<=masked<=n:
            raise RuntimeError('UNIQUE_ACTUAL_FIELD_CANONICAL_NEW_MASK_COUNTS_REQUIRED')
        seen.add(field)
        # Source NA, component fractions and robust-z review are not new masks.
        # Count arithmetic makes strictness explicit: exactly1% may continue.
        if 100*masked>n:
            stops.append(dict(field_id=field,field_key=row.get('field_key'),newly_masked_records=masked,
                              canonical_records=n,fraction=masked/n))
    if stops:
        raise RuntimeError('TASKBOOK_ANOMALOUS_NEW_MASK_GT_1PCT_STOP_REPORT_USER '+json.dumps(stops,sort_keys=True))