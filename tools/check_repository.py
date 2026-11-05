#!/usr/bin/env python3
"""Check the Git source tree without importing or executing project scripts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
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
SECRET_PATTERNS = (
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{20,}'),
    re.compile(rb'github_pat_[A-Za-z0-9_]{20,}'),
    re.compile(rb'sk-[A-Za-z0-9]{20,}'),
    re.compile(rb'-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----'),
    re.compile(rb'(?:WANDB_API_KEY|password)\s*=\s*[\x22\x27][A-Za-z0-9_!@#$%^&*+=.-]{8,}[\x22\x27]', re.I),
)

MODEL_RESULT_REQUIRED = (
    'run_id', 'stage', 'config_sha256', 'code_sha', 'data_version', 'seed',
    'gpu_model', 'elapsed_seconds', 'status', 'preregistration_sha',
)
MODEL_RESULT_OPTIONAL = {
    'gpu_uuid', 'dev_score', 'denoise_rmse', 'throughput_molecules_s',
    'peak_memory_bytes', 'allocated_cpu_seconds', 'allocated_gpu_seconds',
}


def model_summary_csv(name: str, raw: bytes) -> bool:
    """Allow only small, typed, one-row-per-run model experiment summaries."""
    if not re.fullmatch(r'docs/model_v3/results/[A-Za-z0-9][A-Za-z0-9_.-]*\.csv', name):
        return False
    if len(raw) > 128 * 1024 or b'\x00' in raw:
        return False
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8')))
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or not set(MODEL_RESULT_REQUIRED) <= set(fields):
            return False
        numeric = set(MODEL_RESULT_OPTIONAL) - {'gpu_uuid'}
        for field in fields:
            if field not in MODEL_RESULT_REQUIRED and field not in MODEL_RESULT_OPTIONAL:
                if not re.fullmatch(r'metric__[A-Za-z][A-Za-z0-9_]{0,79}', field):
                    return False
                numeric.add(field)
        seen = set()
        rows = 0
        for row in reader:
            rows += 1
            if rows > 2000 or None in row or any(value is None for value in row.values()):
                return False
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', row['run_id']) or row['run_id'] in seen:
                return False
            seen.add(row['run_id'])
            if row['stage'] not in {'1', '2', '3', '4', '5', '6', '7'}:
                return False
            if not re.fullmatch(r'[0-9a-f]{64}', row['config_sha256']):
                return False
            if any(not re.fullmatch(r'[0-9a-f]{40}', row[key]) for key in ('code_sha', 'preregistration_sha')):
                return False
            if not re.fullmatch(r'[A-Za-z0-9_./:+-]{1,128}', row['data_version']):
                return False
            if not row['seed'].isascii() or not row['seed'].isdecimal() or int(row['seed']) > 2**63-1:
                return False
            if not re.fullmatch(r'[A-Za-z0-9 ._+()/-]{1,80}', row['gpu_model']):
                return False
            if row['status'] not in {'PREPARED', 'RUNNING', 'COMPLETED', 'FAILED',
                                     'TIMEOUT', 'CANCELLED', 'NOT_ACCEPTED', 'GUIDE_STOP'}:
                return False
            elapsed = float(row['elapsed_seconds'])
            if not math.isfinite(elapsed) or elapsed < 0:
                return False
            if row.get('gpu_uuid') and not re.fullmatch(r'GPU-[0-9a-fA-F-]{16,64}', row['gpu_uuid']):
                return False
            for key in numeric:
                value = row.get(key, '')
                if value and not math.isfinite(float(value)):
                    return False
                if value and key in {'denoise_rmse', 'throughput_molecules_s', 'peak_memory_bytes',
                                     'allocated_cpu_seconds', 'allocated_gpu_seconds'} and float(value) < 0:
                    return False
                if value and key in {'peak_memory_bytes', 'allocated_cpu_seconds', 'allocated_gpu_seconds'}:
                    if not value.isascii() or not value.isdecimal():
                        return False
        return 0 < rows <= 2000
    except (UnicodeError, ValueError, csv.Error, OverflowError):
        return False


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
        raw = path.read_bytes()
        allowed_summary = path.suffix == '.csv' and model_summary_csv(name, raw)
        if ((path.suffix.lower() in HEAVY_SUFFIXES and not allowed_summary)
                or path.name in {'.env', '.netrc', '.npmrc'}):
            errors.append({'path': name, 'reason': 'data, weights, archive, or credentials file'})
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
