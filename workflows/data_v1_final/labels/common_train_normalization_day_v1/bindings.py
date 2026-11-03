"""Original scientific objects; eligibility and storage are explicit IO seams."""
from workflows.data_v1_final.labels.normalization_compact_runtime_v3.bindings import (
    RadixCounts,advance,initial_queries,TSQR,merge_qr,WinsorMoments,train_values,
    views,inventory,JointMoments,combine,combine_joint,verify_function_objects,
    evaluate,quality_stop_fields,pair_keys,legacy,compact,TASKS,ROLES,
    lookup_batch,classify_owner,sqlite_ro,source_columns,decode,moment_state)
from workflows.data_v1_final.labels.payload_audit_v1.payload import reference_review,worst_preview
from workflows.data_v1_final.labels.normalization_v1 import series,moments

def verify():
    verify_function_objects()
    assert views is series.views and inventory is series.inventory
    assert JointMoments is moments.JointMoments and combine is moments.combine
    assert combine_joint is moments.combine_joint
    return {'scientific_objects':'ORIGINAL_DIRECT_OBJECTS','TSQR_chunk':256,
            'merge':'ORIGINAL_OWNER_GROUP_ORDERED_LEFT_FOLD','patched_original_globals':False}
