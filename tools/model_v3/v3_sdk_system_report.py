"""Readable hardware series from real closed W&B0.28 SDK statistics."""
import json
import math
from pathlib import Path
from wandb.sdk.internal.datastore import DataStore
from wandb.proto import wandb_internal_pb2


def clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def numeric(value, prefix=''):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from numeric(item, prefix + ('.' if prefix else '') + str(key))
    elif type(value) in (float, int) and math.isfinite(value):
        yield prefix, float(value)


def export_system_reports(roots, jobs, destination, capacity_check):
    from phychem_mfm.phase1.v2_disk import save_metadata_json
    output = Path(destination) / 'system_reports'
    raw_size = sum(p.stat().st_size for root in roots for p in root.rglob('*.wandb') if not p.is_symlink())
    capacity_check(2*raw_size + 1024**2, len(roots)*3+2)
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'SYSTEM_REPORT_INDEX.json').exists():
        return output
    index = []
    for occurrence, root in enumerate(roots):
        job = int(root.name)
        stem = str(job) + '_' + str(occurrence)
        target, summary_path = output / (stem + '.jsonl'), output / (stem + '.summary.json')
        if summary_path.exists():
            index.append(json.loads(summary_path.read_text()))
            continue
        columns, count, failure = {}, 0, None
        partial = target.with_suffix(target.suffix + '.partial')
        if partial.exists() or target.exists():
            raise FileExistsError('Retain an incomplete previous derived report; use a new archive attempt directory')
        try:
            with partial.open('x') as stream:
                for path in sorted(root.rglob('*.wandb')):
                    if path.is_symlink():
                        continue
                    data = DataStore()
                    data.open_for_scan(str(path))
                    try:
                        while True:
                            payload = data.scan_data()
                            if payload is None:
                                break
                            record = wandb_internal_pb2.Record()
                            record.ParseFromString(payload)
                            if not record.HasField('stats'):
                                continue
                            values = {}
                            for item in record.stats.item:
                                try:
                                    values[item.key] = clean(json.loads(item.value_json))
                                except (ValueError, TypeError):
                                    values[item.key] = item.value_json
                            timestamp = record.stats.timestamp.seconds + record.stats.timestamp.nanos / 1e9
                            row = dict(timestamp_utc_seconds=timestamp, stats_type=int(record.stats.stats_type),
                                       source_file=str(path), values=values)
                            stream.write(json.dumps(row, allow_nan=False) + '\n')
                            count += 1
                            for key, value in numeric(values):
                                old = columns.setdefault(key, dict(count=0, total=0., minimum=value, maximum=value, last=value))
                                old['count'] += 1
                                old['total'] += value
                                old['minimum'] = min(old['minimum'], value)
                                old['maximum'] = max(old['maximum'], value)
                                old['last'] = value
                    finally:
                        if hasattr(data, 'close'):
                            data.close()
        except Exception as error:
            failure = type(error).__name__ + ': ' + str(error)
        partial.rename(target)
        for column in columns.values():
            column['mean_observed'] = column.pop('total') / column['count']
        summary = dict(job=job, source_sdk_directory=str(root), raw_series=str(target),
            statistics_records=count, statistics_available=count > 0,
            unavailable_reason=('No native SDK statistics records' if count == 0 and failure is None else failure),
            native_metric_names_and_units_preserved=True,
            metrics=columns, parsing_error=failure, selection_use=False,
            interpretation='Descriptive observed mean/min/max; no model-selection or GPU-time gate',
            original_SDK_files_modified=False)
        save_metadata_json(summary, summary_path)
        index.append(summary)
        if failure:
            print('SYSTEM_REPORT_UNRESOLVED', job, failure, flush=True)
    save_metadata_json(dict(reports=index, jobs=jobs, selection_use=False),
                       output / 'SYSTEM_REPORT_INDEX.json')
    return output

