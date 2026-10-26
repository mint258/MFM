"""Independent native offline SDK verification, using the immutable archive-v7 reader."""
from __future__ import annotations

import hashlib
import importlib.metadata
import inspect
from pathlib import Path
import time

import feedback_schema as schema


class Sink:
    """Hash every normalized scientific value in the reader without exporting rows."""
    def write(self, raw): return len(raw)


def installed_source(path):
    # Installed package sources can legitimately be package-manager hard links.
    path = Path(path).resolve(strict=True); before = path.stat()
    schema.require(path.is_file() and before.st_size <= 32 << 20, 'Bounded installed decoder source required')
    digest = hashlib.sha256(path.read_bytes()).hexdigest(); after = path.stat()
    schema.require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
        == (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns), 'Installed decoder source changed')
    return {'path':str(path),'bytes':before.st_size,'sha256':digest}


class Audit:
    def __init__(self, reader, context):
        self.reader, self.context = reader, context
        self.config, self.summary, self.names = {}, {}, []
        self.history_started = False

    def update(self, target, value):
        updates = self.reader.native_items(value.update)
        for item in (*value.remove,*value.update):
            schema.require(not (item.key and item.nested_key), 'Ambiguous native config/summary key')
            key = item.key or '/'.join(item.nested_key)
            schema.require(key, 'Empty native config/summary key')
            for prior in tuple(target):
                if prior == key or prior.startswith(key+'/'): target.pop(prior)
        target.update(updates)

    @staticmethod
    def public(values):
        result = {}
        for key, value in values.items():
            if key.startswith('_'):
                schema.require(key in ('_step','_runtime','_timestamp','_wandb') or key.startswith('_wandb/'),
                    'Unexpected private native config/summary field')
            else: result[key] = value
        return result

    def check_config(self):
        expected = self.reader.flatten(self.context['expected_config']); actual = self.public(self.config)
        schema.require(set(actual) == set(expected), 'Missing or extra public native config')
        for key, value in expected.items(): self.reader.typed_like(actual[key],value)

    def observe(self, record):
        kind = record.WhichOneof('record_type')
        if kind == 'run':
            self.names.append(record.run.display_name); self.update(self.config,record.run.config)
            if self.history_started: self.check_config()
        elif kind == 'config':
            self.update(self.config,record.config)
            if self.history_started: self.check_config()
        elif kind == 'summary': self.update(self.summary,record.summary)
        elif kind == 'history': self.check_config(); self.history_started = True

    def finish(self):
        self.check_config()
        schema.require(self.names == [self.context['run_name']], 'Native display name differs')
        expected = {}
        for row in self.context['expected_rows']: expected.update(self.reader.flatten(row['row']))
        actual = self.public(self.summary)
        schema.require(set(actual) == set(expected), 'Missing or extra public native summary')
        for key, value in expected.items(): self.reader.typed_like(actual[key],value)
        schema.require(type(self.summary.get('_step')) is int and self.summary['_step'] == 16,
            'Native final summary explicit step differs')


def compare(data, record_class, context, *, deadline=None, **limits):
    """No model/target access; metadata-only synthetic protobuf tests use this boundary."""
    reader = schema.reader(); audit = Audit(reader,context)
    class TappedRecord:
        def __init__(self): self.record = record_class()
        def ParseFromString(self, raw): self.record.ParseFromString(raw); audit.observe(self.record)
        def __getattr__(self, key): return getattr(self.record,key)
    expected = [{'step':row['step'],'row':reader.flatten(row['row'])} for row in context['expected_rows']]
    verdict = reader.verify_stream(data,TappedRecord,Sink(),expected_run_id=context['run_id'],expected_exit=0,
        expected_rows=17,mirror_factory=lambda _:iter(expected),deadline=deadline,**limits)
    audit.finish()
    schema.require(verdict['native_closed'] is True and verdict['history_rows'] == 17
        and verdict['first_explicit_step'] == 0 and verdict['last_explicit_step'] == 16,
        'Closed seventeen-row diagnostic stream required')
    return verdict


def verify(context, *, deadline=None):
    started = time.monotonic(); deadline = started+schema.LIMITS['max_wall_seconds'] if deadline is None else deadline
    from wandb.proto import wandb_internal_pb2
    from wandb.sdk.internal.datastore import DataStore
    sdk = schema.bind(context['SDK_file'],schema.LIMITS['max_source_bytes']); data = DataStore()
    try:
        data.open_for_scan(str(sdk))
        verdict = compare(data,wandb_internal_pb2.Record,context,deadline=deadline,
            **{key:schema.LIMITS[key] for key in ('max_native_records','max_history_rows','max_record_bytes','max_export_bytes')})
    finally: data.close()
    for ref in context['all_refs']:
        schema.bind(ref,schema.LIMITS['max_source_bytes'] if ref == context['SDK_file'] else schema.FILE_CAP)
    schema.require(time.monotonic() <= deadline, 'Inclusive verification wall budget exhausted')
    return {'schema':'model_v3_A06_feedback_native_verification_v1','status':'VERIFIED_DIAGNOSTIC_ONLY',
        'job_id':schema.JOB,'run_id':context['run_id'],'run_name':context['run_name'],
        'scientific_acceptance':False,'A06_original_gate_status':'FAILED_UNCHANGED',
        'expectation_origin':'fixed logger reconstruction from saved detailed aggregates, independently matched to mirror and saved457 scalar histories',
        'all_public_metrics_config_summary_steps_exact':True,'verified_explicit_steps':list(range(17)),
        'expected_history_sha256':schema.canonical(context['expected_rows']),
        'expected_config_sha256':schema.canonical(context['expected_config']),
        'actual_source_inventory_sha256':context['source_inventory_sha256'],
        'actual_source_inventory_count':context['source_inventory_count'],
        'actual_source_inventory_bytes':context['source_inventory_bytes'],
        'fixed_logger_source':schema.file_ref(schema.PRODUCER),'bounded_reader_source':schema.file_ref(schema.READER),
        'verifier_source':schema.file_ref(__file__),'WandB_version':importlib.metadata.version('wandb'),
        'SDK_decoder_sources':{'DataStore':installed_source(inspect.getfile(DataStore)),
            'Record_module':installed_source(wandb_internal_pb2.__file__)},
        'SDK_file':context['SDK_file'],'native':verdict,'actual_parent_accounting':context['accounting'],
        'metadata_bindings':context['sources'],'update_bindings':context['update_refs'],
        'Root_operational_bindings':context.get('root_operational_bindings',{}),
        'limits':schema.LIMITS,'elapsed_seconds':time.monotonic()-started,
        'online_sync_performed':False,'SDK_original_modified':False,'native_geometry_or_targets_opened':False,
        'parameter_arrays_or_member_ids_exported':False}
