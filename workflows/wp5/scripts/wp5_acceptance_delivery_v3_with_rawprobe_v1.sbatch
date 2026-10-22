#!/bin/bash
#SBATCH --job-name=wp5_delivery3_raw
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --nodelist=compute-0-17
#SBATCH --chdir=/share/home/zixiao/descriptor_analysis
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/delivery3_with_rawprobe_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/delivery3_with_rawprobe_%j.err
# Root alone submits after actual prerequisite closure. No future terminal rows.
# First positional argument is raw union sacct JSON, separate from delivery --accounting.
set -euo pipefail
cd /share/home/zixiao/descriptor_analysis
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=""
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
FINAL="$ROOT/acceptance/final_20261016_v1"
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
terminal_union_accounting=${1:?actual terminal union accounting JSON required}
shift
[[ "$(id -u)" == 1278 && "$(hostname -s)" == compute-0-17 ]] || exit 2
[[ "${SLURM_JOB_ID:-}" =~ ^[0-9]+$ && "${SLURM_CPUS_PER_TASK:-}" == 24 ]] || exit 2
[[ -f "$terminal_union_accounting" && -r "$terminal_union_accounting" ]] || exit 2
"$PY" -B - "$ROOT" <<'PY'
import hashlib, sys
from pathlib import Path
root = Path(sys.argv[1])
pins = {
    "wp5_three_historical_raw_metadata_probe_v1.py": "7875804d7011a79750c9407a1779a15a74559b33b777ccc929645ccbdd533f88",
    "wp5_acceptance_delivery_v3.py": "d8af3311a0de17cec43df7f93a4613dfca99c69d6f5ca6af219fed6921516aaa",
}
for name, expected in pins.items():
    if hashlib.sha256((root / "scripts" / name).read_bytes()).hexdigest() != expected:
        raise ValueError("FROZEN_SOURCE_SHA_DIFFERS:" + name)
PY
probe_dir="$FINAL/extra3_raw_probe_$SLURM_JOB_ID"
mkdir -- "$probe_dir"
timeout --signal=TERM --kill-after=60s 5m "$PY" -B "$ROOT/scripts/wp5_three_historical_raw_metadata_probe_v1.py" \
  --catalog "$FINAL/catalog/catalog.json" --terminal-accounting "$terminal_union_accounting" \
  --out "$probe_dir/historical_raw_probe.json"
# One actual metadata reference row for the future index manifest.references.
# This row alone is not the complete required-role supplemental manifest.
"$PY" -B - "$probe_dir" <<'PY'
import hashlib, json, os, sys
from pathlib import Path
folder = Path(sys.argv[1])
report = folder / "historical_raw_probe.json"
row = {
    "role": "historical_raw_container_probe",
    "path": str(report),
    "sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
    "note": "Three retained historical raw containers; metadata/schema/counts only. "
            "Report classification remains authoritative; no addition to canonical SCI.",
}
with (folder / "index_supplemental_reference.json").open("x") as stream:
    json.dump(row, stream, sort_keys=True, indent=2, allow_nan=False)
    stream.write("\n")
    stream.flush()
    os.fsync(stream.fileno())
PY
# 5m probe + 45h delivery + both 60s kill grace periods remain below 46h.
# Raw files are retained. Delivery3 receives its unchanged evidence CLI and creates --out.
exec timeout --signal=TERM --kill-after=60s 45h "$PY" -B "$ROOT/scripts/wp5_acceptance_delivery_v3.py" \
  --workers 24 "$@" --out "$FINAL/delivery_$SLURM_JOB_ID"
