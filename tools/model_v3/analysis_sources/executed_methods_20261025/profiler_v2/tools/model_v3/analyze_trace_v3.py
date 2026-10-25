"""Analyze one immutable profiler trace; write a compact attribution report."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT / "current"))


def main():
    from phychem_mfm.model.v3_profiler_attribution import analyze_trace
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-budget-bytes", type=int, default=2 * 1024**3)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Keep prior attribution artifacts; use a fresh output path")
    if args.trace.parent != args.output.parent or not 32 * 1024**2 <= args.output_budget_bytes <= 2 * 1024**3:
        raise ValueError("Keep compact analysis beside its trace under the original bounded output root")
    descriptor = os.open(args.trace, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or before.st_size > 2 * 1024**3:
            raise ValueError("Owned ordinary trace within2GiB required")
        raw = stream.read(2 * 1024**3 + 1)
        after = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or len(raw) != after.st_size:
            raise ValueError("Trace changed during attribution binding")
    trace = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    result = analyze_trace(trace)
    result["trace_binding"] = {"path": str(args.trace.absolute()), "bytes": len(raw),
                               "sha256": hashlib.sha256(raw).hexdigest()}
    result["analysis_source_sha256"] = {"tools/model_v3/analyze_trace_v3.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "current/phychem_mfm/model/v3_profiler_attribution.py": hashlib.sha256(
            (ROOT / "current/phychem_mfm/model/v3_profiler_attribution.py").read_bytes()).hexdigest()}
    encoded = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    from runtime_monitor import owned_output_bytes
    if len(encoded) > 16 * 1024**2 or owned_output_bytes(args.output.parent) + len(encoded) > args.output_budget_bytes - 1024**2:
        raise MemoryError("Compact attribution would exceed the original output budget")
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"unique_kernel_events": result["unique_kernel_events"],
                      "duplicate_kernel_events_removed": result["duplicate_kernel_events_removed"]}))


if __name__ == "__main__":
    main()
