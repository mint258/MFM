"""Pure measured-profile resource projections, explicitly not worst-case proofs."""
from decimal import Decimal
from fractions import Fraction
import math

N=124857440;PARTS=500;MAX_PART_ROWS=250000;DRAIN=(1<<30)+(128<<20);DISPATCH_RESERVE=120


def need(value,message):
    if not value:raise ValueError(message)


def ratio(value):
    need(type(value) in (str,int,float),'EXPLICIT_FINITE_RESOURCE_NUMBER')
    if type(value) is float:
        need(math.isfinite(value),'FINITE_REPORTED_RESOURCE_NUMBER');return Fraction.from_float(value)
    value=str(value);need(len(value)<=128,'BOUNDED_DECIMAL_RESOURCE_NUMBER');number=Decimal(value)
    need(number.is_finite() and abs(number.as_tuple().exponent)<=128,'FINITE_BOUNDED_DECIMAL_RESOURCE_NUMBER');return Fraction(number)


def ceil(value):return -((-value.numerator)//value.denominator)
def exact(value):return {'numerator':value.numerator,'denominator':value.denominator}


def partition(value):
    need(value['schema']=='ALPHA_PUBCHEM_EXCLUSIVE_ORDINAL_MANIFEST_V1' and value['population_N']==N and value['part_count']==PARTS
        and value['pool_release_authorized'] is False and len(value['shards'])==PARTS,'EXACT_FULL500_METADATA_PARTITION')
    first=1
    for index,row in enumerate(value['shards']):
        need(all(type(row[key]) is int for key in ('shard_index','first_part','last_part','first_ordinal','last_ordinal')),'ACTUAL_INTEGER_PARTITION_BOUNDS')
        need(row['shard_index']==row['first_part']==row['last_part']==index and row['first_ordinal']==first
            and type(row['last_ordinal']) is int and 1<=row['last_ordinal']-first+1<=MAX_PART_ROWS,'ONE_PART_CONTIGUOUS_NO_HOLE_OR_OVERLAP')
        first=row['last_ordinal']+1
    need(first==N+1,'ALL_RAW_ORDINALS_EXACTLY_ONCE_IN_FROZEN_METADATA')
    return value


def measured(uniform):
    need(uniform['group']=='uniform10000' and uniform['completed_rows']==uniform['dispatched_rows']==10000
        and uniform['counts']=={'accepted':8773,'chemReject':1223,'technicalUnresolved':4}
        and sum(uniform['worker_records'].values())==10000 and len(uniform['worker_records'])==16 and min(uniform['worker_records'].values())>0,'ACTUAL_UNIFORM10000_SCIENTIFIC_SCOPE')
    event=uniform['full_dispatch_and_result_journal'];parquet=uniform['features']
    need(type(event['bytes']) is int and event['bytes']>0 and type(parquet['bytes']) is int and parquet['bytes']>0,'ACTUAL_UNIFORM_EVENT_AND_PARQUET_BYTES')
    sums=uniform['worker_task_phase_sums'];audit=ratio(sums['audit_CPU_seconds']);dispatch=ratio(sums['dispatcher_CPU_seconds_includes_legacy_X_parse'])
    phase=ratio(uniform['phase_wall_seconds']);need(audit>=0 and dispatch>=0 and phase>0,'ACTUAL_SEPARATE_UNIFORM_PHASE_MEASUREMENTS')
    return {'rows':10000,'event_reference':event,'Parquet_reference':parquet,'row_payload_bytes':event['bytes']+parquet['bytes'],
        'audit_CPU':audit,'dispatcher_CPU_including_legacy_X':dispatch,'uniform_phase_wall':phase}


def reviewed_limits(source,root,rows):
    need(type(rows) is int and 0<rows<=MAX_PART_ROWS,'FINITE_ACTUAL_PART_ROWS')
    expansion=ratio(root['output_expansion_factor']);wall_factor=ratio(root['wall_expansion_factor'])
    admin=root['admin_reserved_bytes'];wall=root['wall_seconds'];cap=root['output_cap_bytes'];io=root['root_IO_and_startup_allowance_seconds']
    need(expansion>=1 and wall_factor>=1 and type(admin) is int and admin>0 and type(io) is int and io>=0,'ROOT_EXPLICIT_MARGIN_ADMIN_AND_IO_CHOICES')
    need(type(wall) is int and 0<wall<=172800 and wall%60==0 and type(cap) is int and 0<cap<=1<<40,'ROOT_EXPLICIT_WHOLE_MINUTE_WALL_AND_WHOLE_CAP')
    payload=ceil(Fraction(source['row_payload_bytes']*rows,source['rows'])*expansion)
    minimum=payload+DRAIN+admin
    need(cap>=minimum,'ROOT_CAP_BELOW_UNIFORM_DERIVED_PAYLOAD_PLUS_FIXED_DRAIN_PLUS_ADMIN')
    basis=root['wall_projection_basis']
    if basis=='UNIFORM_PHASE_WALL_ROW_SCALED_REFERENCE':
        reference=source['uniform_phase_wall']*rows/source['rows']
    elif basis=='UNIFORM_WORKER_CPU_AT16_PLUS_ROOT_IO_ALLOWANCE':
        reference=(source['audit_CPU']+source['dispatcher_CPU_including_legacy_X'])*rows/(source['rows']*16)
    else:raise ValueError('EXPLICIT_SUPPORTED_WALL_REFERENCE_BASIS_REQUIRED')
    minimum_wall=ceil(reference*wall_factor)+io+DISPATCH_RESERVE
    need(wall>=minimum_wall,'ROOT_WALL_BELOW_CHOSEN_MEASURED_REFERENCE_MARGIN_IO_AND_DISPATCH_RESERVE')
    return {'expected_rows':rows,'uniform_rows':source['rows'],'uniform_event_plus_Parquet_bytes':source['row_payload_bytes'],
        'uniform_bytes_per_row_exact':exact(Fraction(source['row_payload_bytes'],source['rows'])),
        'root_output_expansion_factor_exact':exact(expansion),'projected_payload_bytes_after_margin':payload,
        'fixed_pending_drain_bytes':DRAIN,'root_admin_reserved_bytes':admin,'minimum_profile_derived_output_cap_bytes':minimum,
        'wall_projection_basis':basis,'chosen_wall_reference_seconds_exact':exact(reference),'root_wall_expansion_factor_exact':exact(wall_factor),
        'root_IO_and_startup_allowance_seconds':io,'fixed_dispatch_reserve_seconds':DISPATCH_RESERVE,
        'minimum_chosen_wall_reference_seconds':minimum_wall,'wall_seconds':wall,'output_cap_bytes':cap,
        'mean_projection_is_not_worst_case':True,'worst_case_feature_size_proven':False,
        'uniform_phase_wall_includes_selected_part_hash_read_and_writer_overhead':True,
        'worker_CPU_sums_not_parent_allocation_cost':True,'longest16_or_total_bundle_bytes_in_mean':False,
        'uniform_group_receipt_comparison_journal_fixtures_worker_logs_in_row_mean':False}
