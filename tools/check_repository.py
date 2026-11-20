#!/usr/bin/env python3
"""Check the Git source tree without importing or executing project scripts."""
from __future__ import annotations

import argparse
import csv
import io
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HEAVY_SUFFIXES = {
    '.pt', '.pth', '.ckpt', '.safetensors', '.onnx', '.bin', '.lmdb', '.mdb',
    '.parquet', '.arrow', '.feather', '.sqlite', '.sqlite3', '.db',
    '.npy', '.npz', '.pkl', '.pickle', '.xyz', '.sdf', '.mol',
    '.tar', '.gz', '.bz2', '.xz', '.zip', '.7z', '.h5', '.hdf5', '.csv',
}
# Exact aggregate deliverables authorized by the downstream benchmark taskbook.
# Raw labels, molecular identities and per-record predictions remain outside Git.
BENCHMARK_REPORT_TABLES = {
    'results/benchmark/B1_task_screen.csv': {'endpoint_key', 'decision', 'reason'},
    'results/benchmark/B1_filter_impact.csv': {'endpoint_key', 'model', 'fit_population', 'evaluation_population'},
    'results/benchmark/B1_scaffold_Tukey_HSD.csv': {'endpoint_key', 'left', 'right', 'pvalue'},
    'results/benchmark/B1_Chemprop_paired_comparisons.csv': {'endpoint_key', 'reference_model', 'candidate_model', 'significant_improvement'},
    'results/benchmark/B1_Chemprop_seed2_plan.csv': {'endpoint_key', 'model', 'reason', 'confirmation_seed'},
    'results/benchmark/PPE_native_classical_baselines.csv': {'dataset', 'method', 'MAE', 'RAE_TRAIN_mean'},
    'results/benchmark/C1_results.csv': {'endpoint_key', 'feature_group', 'learner', 'report_stage', 'model_seed'},
    'results/benchmark/C1_second_seed_registered_comparisons.csv': {'endpoint_key', 'feature_group', 'learner', 'comparison'},
    'results/benchmark/B1_Chemprop_confirmation_results.csv': {'endpoint_key', 'model', 'confirmation_status'},
}
RECORD_DATA_COLUMNS = frozenset(('record_id', 'evaluation_id', 'full_inchikey', 'smiles', 'y_true', 'prediction'))

def report_csv_error(name, raw):
    """Check aggregate export shape only; never recalculate scientific statistics."""
    try:
        rows = csv.reader(io.StringIO(raw.decode('utf-8')))
        header = next(rows)
        if len(set(header)) != len(header):
            return 'duplicate aggregate report columns'
        if RECORD_DATA_COLUMNS.intersection(field.strip().lower() for field in header):
            return 'individual molecular data or predictions are not aggregate reports'
        if (name == 'results/benchmark/C1_second_seed_registered_comparisons.csv'
                and header == ['status'] and next(rows, None) is None):
            return None  # A closed zero-required comparison export has only this header.
        if not BENCHMARK_REPORT_TABLES[name].issubset(header):
            return 'aggregate benchmark report header differs from its registered role'
    except (UnicodeError, csv.Error, StopIteration):
        return 'invalid aggregate benchmark CSV'
    return None

SECRET_PATTERNS = (
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{20,}'),
    re.compile(rb'github_pat_[A-Za-z0-9_]{20,}'),
    re.compile(rb'sk-[A-Za-z0-9]{20,}'),
    re.compile(rb'-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----'),
    re.compile(rb'(?:WANDB_API_KEY|password)\s*=\s*[\x22\x27][A-Za-z0-9_!@#$%^&*+=.-]{8,}[\x22\x27]', re.I),
)


def check(root: Path, paths: list[str], *, verify_export=True) -> dict:
    errors = []
    source_manifest = json.loads((root / 'docs/SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    references = {row['path']: row for row in source_manifest['files']}
    total = python_files = matched_sources = 0
    for name in sorted(set(paths)):
        path = root / name
        if not path.is_file():
            continue
        if path.is_symlink():
            errors.append({'path': name, 'reason': 'symlinks cannot package external assets'})
            continue
        size = path.stat().st_size
        if size > 2 * 1024 * 1024:
            errors.append({'path': name, 'reason': 'exceeds the 2 MiB source-file limit'})
            continue
        if ((path.suffix.lower() in HEAVY_SUFFIXES and name not in BENCHMARK_REPORT_TABLES)
                or path.name in {'.env', '.netrc', '.npmrc'}):
            errors.append({'path': name, 'reason': 'data, weights, archive, or credentials file'})
            continue
        raw = path.read_bytes()
        if name in BENCHMARK_REPORT_TABLES:
            report_error = report_csv_error(name, raw)
            if report_error:
                errors.append({'path': name, 'reason': report_error})
                continue
        total += len(raw)
        if any(pattern.search(raw) for pattern in SECRET_PATTERNS):
            errors.append({'path': name, 'reason': 'possible embedded credential; value withheld'})
        if path.suffix == '.py':
            python_files += 1
            try:
                compile(raw, name, 'exec')
            except (SyntaxError, ValueError) as exc:
                errors.append({'path': name, 'reason': 'Python syntax error', 'line': getattr(exc, 'lineno', None)})
        if name in references:
            row = references[name]
            if size != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
                if not verify_export:
                    continue
                errors.append({'path': name, 'reason': 'differs from the exported server source'})
            else:
                matched_sources += 1
    missing = sorted(set(references) - set(paths))
    if verify_export:
        errors.extend({'path': name, 'reason': 'manifest source absent from Git tree'} for name in missing)
    return {'status': 'PASS' if not errors else 'FAIL', 'files': len(set(paths)),
            'bytes': total, 'python_files': python_files,
            'server_sources_verified': matched_sources,
            'export_verification_required': verify_export, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify-export', action='store_true', help='Require the original exported server bytes')
    args = parser.parse_args()
    root = args.root.resolve()
    output = subprocess.check_output(
        ['git', '-C', str(root), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'])
    result = check(root, [name.decode('utf-8') for name in output.split(b'\0') if name], verify_export=args.verify_export)
    text = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(text, end='')
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
