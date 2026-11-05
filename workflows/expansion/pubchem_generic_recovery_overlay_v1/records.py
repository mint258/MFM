"""Convert only existing strict diagnostic records, retaining their original lineage."""
import hashlib
import json
import os
from pathlib import Path
import struct
from ..alpha_runtime_v1 import common as Q
from ..pubchem_closed500_bulk_v2.schema import FLOAT_FEATURES,INT_FEATURES,TEXT_FEATURES
from .runtime import VERSION,REPRESENTATION

FEATURES={'cid','ordinal','reasons','source_smiles','elements','generic_ring_systems',*FLOAT_FEATURES,*INT_FEATURES,*TEXT_FEATURES}


def convert(raw,data_ref,line_number,offset):
    d=json.loads(raw);source=d['source'];original=source['observation'];old=original['original_typed_fields']
    Q.need(d['schema']=='PUBCHEM_GENERIC_UNKNOWN_NATIVE_DIAGNOSTIC_ROW_V1'
        and d['diagnostic_status']=='REPAIRED_CANDIDATE_NON_GENERIC_EXACT'
        and d['non_generic_field_set_equal'] is True and d['exact_non_generic_differences']=={}
        and d['original_template_snapshot_equal_after'] is True
        and d['whole_source_SMILES_SHA_equal'] is True and d['original_failure_type_message_equal_recorded'] is True
        and d['original_technical_UNKNOWN_retained'] is True and d['scientific_acceptance'] is False,
        'Every actual native diagnostic strict comparison passed without old-row mutation')
    Q.need(d['representation_version']==REPRESENTATION and d['representation_repair_applied'] is True
        and d['original_kernel_passed'] is False and d['original_failure']['type']=='AtomValenceException'
        and any(e.get('heavy_adjacency_allC_SINGLE_verified') is True for e in d['generic_events']),
        'Exact same witnessed generic representation repair')
    evaluation=json.loads(d['native_evaluation_JSON_text']);f=evaluation['features'];expected=d['non_generic_expected']
    Q.need(set(f)==FEATURES and Q.canonical({k:v for k,v in f.items() if k not in {'generic_murcko','generic_ring_systems'}})==Q.canonical(expected)
        and evaluation['version']==REPRESENTATION and evaluation['representation_repair_applied'] is True
        and evaluation['original_error']==d['original_failure'] and evaluation['events']==d['generic_events'],
        'Complete diagnostic evaluation matches exact non-generic expectations and provenance')
    Q.need(old['category']=='technicalUnresolved' and old['audit_parse_succeeded'] is True
        and old['ordinal']==f['ordinal'] and old['cid_source_ascii'].isdigit()
        and int(old['cid_source_ascii'])==f['cid'] and f['cid']>0 and f['reasons']==[]
        and old['source_smiles']==f['source_smiles']
        and hashlib.sha256(f['source_smiles'].encode('utf-8')).hexdigest()==old['source_smiles_sha256'],
        'Exact original UNKNOWN CID/ordinal/whole-SMILES binding')
    flags=json.loads(old['audit_flags_json'])
    Q.need(flags==d['original_X_flags']==d['after_original_X_flags']
        and set(flags)=={'X01','X02','X03','X04','X05'} and all(v is False for v in flags.values()),
        'Exact unchanged original allFalse X policy')
    row={k:old[k] for k in ('ordinal','cid_source_ascii','source_smiles','source_smiles_sha256',
        'source_part_reference_json','audit_parse_succeeded','audit_flags_json',
        'audit_X01','audit_X02','audit_X03','audit_X04','audit_X05')}
    row.update(sample_group=VERSION,category='accepted',technical_codes=[],legacy_reasons=[],error_evidence_json='{}',
        full_dispatcher_result_json=Q.canonical(f).decode(),worker_pid=d['worker_pid'],cid=f['cid'],
        source_fragment_id=original['source_fragment_id'])
    for k in (*FLOAT_FEATURES,*INT_FEATURES,*TEXT_FEATURES,'elements','generic_ring_systems'):row[k]=f[k]
    for k in ('audit_wall_seconds','audit_CPU_seconds','dispatcher_wall_seconds_includes_legacy_X_parse',
              'dispatcher_CPU_seconds_includes_legacy_X_parse'):row[k]=None
    floats={k:struct.pack('>d',f[k]).hex() for k in FLOAT_FEATURES}
    lineage=dict(schema='PUBCHEM_GENERIC_RECOVERY_SOURCE_LINEAGE_V1',population_version=VERSION,cid=f['cid'],
        full_key=f['full_key'],source_ordinal=f['ordinal'],source_fragment_id=original['source_fragment_id'],
        native_diagnostic_record=dict(reference=data_ref,ordinal_1based=line_number,byte_offset=offset,
            bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),
        prior_technical_audit_record={k:source[k] for k in ('DATA_reference','record_ordinal_1based','byte_offset','bytes','sha256')},
        original_Parquet_reference=original['source_reference'],original_Parquet_physical_row_0based=original['physical_parquet_row_0based'],
        original_category='technicalUnresolved',new_delta_category='accepted',representation_version=REPRESENTATION,
        original_technical_row_unchanged=True,per_row_timing_fields_null_not_reconstructed=True,
        worker_pid_namespace='original_native_diagnostic1885177',materializer_worker_pid=os.getpid(),binary64_features_hex=floats)
    alias=dict(cid=f['cid'],full_key=f['full_key'],source_ordinal=f['ordinal'],source_fragment_id=original['source_fragment_id'])
    return row,alias,lineage


def initialize(barrier,directory):
    try:
        Q.need(os.getuid()==1264 and os.environ.get('SLURM_JOB_ID'),'Actual Alpha delta worker')
        Q.write(Path(directory)/('worker_%s.json'%os.getpid()),dict(pid=os.getpid(),uid=os.getuid(),
            job_id=os.environ['SLURM_JOB_ID'],chemistry_calls=0))
        barrier.wait()
    except BaseException:barrier.abort();raise
