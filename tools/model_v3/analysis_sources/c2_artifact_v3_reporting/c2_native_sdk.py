"""Independent, offline two-row C2 native SDK verification; no lookup access."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
from pathlib import Path
import time

import c2_artifact_schema as schema

LIMITS = {'max_source_bytes': 128 << 20, 'max_native_records': 500000,
    'max_history_rows': 100000, 'max_record_bytes': 4 << 20,
    'max_export_bytes': 64 << 20, 'max_wall_seconds': 180}


class Sink:
    """The frozen reader hashes all normalized rows; raw history is not exported."""
    def write(self, raw): return len(raw)


def installed_source(path):
    """Read-only library provenance; package-manager hard links are legitimate."""
    path = Path(path).resolve(strict=True); before = path.stat()
    schema.require(path.is_file() and before.st_size <= 32 << 20, 'Bounded installed Python source required')
    digest = hashlib.sha256(path.read_bytes()).hexdigest(); after = path.stat()
    schema.require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'Installed decoder source changed')
    return {'path': str(path), 'bytes': before.st_size, 'sha256': digest}


class Audit:
    def __init__(self, reader, context):
        self.reader, self.context = reader, context
        self.config, self.summary, self.names = {}, {}, []
        self.history_started = False

    def update(self, target, value):
        updates = self.reader.native_items(value.update)
        for item in value.remove:
            schema.require(not (item.key and item.nested_key), 'Ambiguous native removal key')
            key = item.key or '/'.join(item.nested_key)
            for prior in tuple(target):
                if prior == key or prior.startswith(key+'/'): target.pop(prior)
        for item in value.update:
            key = item.key or '/'.join(item.nested_key)
            for prior in tuple(target):
                if prior == key or prior.startswith(key+'/'): target.pop(prior)
        for key, item in updates.items():
            # Replacing a structured config may replace its complete subtree.
            for prior in tuple(target):
                if prior == key or prior.startswith(key+'/'): target.pop(prior)
            target[key] = item

    @staticmethod
    def public(values):
        result = {}
        for key, value in values.items():
            if key.startswith('_'):
                schema.require(key in ('_step', '_runtime', '_timestamp', '_wandb')
                    or key.startswith('_wandb/'), 'Unexpected private native key')
            else: result[key] = value
        return result

    def check_config(self):
        expected = self.reader.flatten(self.context['expected_config'])
        actual = self.public(self.config)
        schema.require(set(actual) == set(expected), 'Missing or extra public native config')
        for key, value in expected.items(): self.reader.typed_like(actual[key], value)

    def observe(self, record):
        kind = record.WhichOneof('record_type')
        if kind == 'run':
            self.names.append(record.run.display_name)
            self.update(self.config, record.run.config)
            if self.history_started: self.check_config()
        elif kind == 'config':
            self.update(self.config, record.config)
            if self.history_started: self.check_config()
        elif kind == 'summary': self.update(self.summary, record.summary)
        elif kind == 'history':
            self.check_config(); self.history_started = True

    def finish(self):
        self.check_config()
        schema.require(self.names == [self.context['run_name']], 'Native display name differs')
        expected = {}
        for row in self.context['expected_rows']: expected.update(row['row'])
        actual = self.public(self.summary)
        schema.require(set(actual) == set(expected), 'Missing or extra public native summary')
        for key, value in expected.items(): self.reader.typed_like(actual[key], value)
        schema.require(type(self.summary.get('_step')) is int and self.summary['_step'] == 1, 'Native final summary step differs')


def compare(data, record_class, context, *, deadline=None, **limits):
    """Use the SHA-pinned archive_v7 decoder plus independent config/summary tap."""
    reader = schema.reader(); audit = Audit(reader, context)

    class TappedRecord:
        def __init__(self): self.record = record_class()
        def ParseFromString(self, raw):
            self.record.ParseFromString(raw); audit.observe(self.record)
        def __getattr__(self, name): return getattr(self.record, name)

    verdict = reader.verify_stream(data, TappedRecord, Sink(), expected_run_id=context['run_id'],
        expected_exit=0, expected_rows=2, mirror_factory=lambda _: iter(context['expected_rows']),
        deadline=deadline, **limits)
    audit.finish()
    schema.require(verdict['native_closed'] is True and verdict['history_rows'] == 2
        and verdict['first_explicit_step'] == 0 and verdict['last_explicit_step'] == 1,
        'Closed native two-row stream required')
    return verdict


def verify(context, *, deadline=None):
    from wandb.proto import wandb_internal_pb2
    from wandb.sdk.internal.datastore import DataStore
    started = time.monotonic(); original = context['SDK_file']
    deadline = started+LIMITS['max_wall_seconds'] if deadline is None else deadline
    observed = schema.file_ref(original['path'], LIMITS['max_source_bytes'])
    schema.require(observed == original, 'Native SDK raw binding differs')
    sdk = Path(observed['path']); root = Path(context['sources']['result']['path']).parent
    schema.require(sdk.is_relative_to(root/'wandb') and sdk.name == 'run-'+context['run_id']+'.wandb',
        'SDK must be the declared run within current output/wandb')
    data = DataStore()
    try:
        data.open_for_scan(str(sdk))
        verdict = compare(data, wandb_internal_pb2.Record, context, deadline=deadline,
            **{key: LIMITS[key] for key in ('max_native_records', 'max_history_rows', 'max_record_bytes', 'max_export_bytes')})
    finally: data.close()
    schema.require(schema.file_ref(sdk, LIMITS['max_source_bytes']) == original, 'SDK changed during scan')
    for ref in context['sources'].values():
        schema.require(schema.file_ref(ref['path']) == ref, 'Bound metadata changed during scan')
    schema.require(time.monotonic() <= deadline, 'Native verification wall budget exhausted')
    return {'schema': 'model_v3_C2_artifact_v3_native_verification_v1', 'status': 'VERIFIED',
        'job_id': context['job_id'], 'run_id': context['run_id'], 'run_name': context['run_name'],
        'expectation_origin': 'code-derived saved outputs; no independent mirrored history file exists',
        'fixed_logger_source_sha256': schema.RUNTIME_SOURCES[schema.PRODUCER.name],
        'fixed_producer_path': str(schema.PRODUCER), 'fixed_runtime_sources_sha256': schema.RUNTIME_SOURCES,
        'expected_two_rows_sha256': hashlib.sha256(b''.join(schema.encoded(row) for row in context['expected_rows'])).hexdigest(),
        'expected_config_sha256': schema.canonical(context['expected_config']),
        'all_public_metrics_config_summary_exact': True, 'verified_steps': [0, 1],
        'reader_source': schema.file_ref(schema.READER), 'verifier_source': schema.file_ref(__file__),
        'WandB_version': importlib.metadata.version('wandb'),
        'SDK_decoder_sources': {'DataStore': installed_source(inspect.getfile(DataStore)),
            'Record_module': installed_source(wandb_internal_pb2.__file__)},
        'SDK_file': observed, 'metadata_bindings': context['sources'], 'native': verdict,
        'limits': LIMITS, 'elapsed_seconds': time.monotonic()-started,
        'scientific_acceptance': False, 'online_sync_performed': False, 'SDK_original_modified': False}


def load_context(path, sha):
    ref = schema.file_ref(path)
    schema.require(ref['sha256'] == sha, 'Report input manifest SHA differs')
    context = schema.prepare(schema.read(ref)); context['sources']['report_inputs'] = ref
    return context


def main(argv=None):
    deadline = time.monotonic()+LIMITS['max_wall_seconds']
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True); parser.add_argument('--inputs-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    context = load_context(args.inputs, args.inputs_sha256)
    certificate = verify(context, deadline=deadline)
    output = Path(args.output)
    schema.require(output.is_absolute() and '..' not in output.parts and not output.exists(), 'Fresh absolute certificate output required')
    for parent in output.parents: schema.require(not parent.is_symlink(), 'Physical output ancestry required')
    with output.open('xb') as stream: stream.write(schema.encoded(certificate))
    print('{"status":"VERIFIED","history_rows":2,"online_sync_performed":false}')


if __name__ == '__main__': main()
