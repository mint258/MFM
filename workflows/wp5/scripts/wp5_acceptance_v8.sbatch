#!/bin/bash
#SBATCH --job-name=wp5_acceptance
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-17
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=32G
#SBATCH --time=48:00:00
#SBATCH --signal=B:USR1@300
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/acceptance_%j.out
#SBATCH --error=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/logs/acceptance_%j.err
set -euo pipefail
ROOT=/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011
mkdir -p -- "$ROOT/acceptance"
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts:${PYTHONPATH:-}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export WP5_NODE_AUTHORITY="$ROOT/gates/wp5_node_replacement_user_approved.json"
export WP5_NODE_SCOPE_PLAN="$ROOT/packing/node_assignment_v3/tasks.json"
STAGE="${1:?acceptance stage required}";shift
case "$STAGE" in
 verify|plan-200)
  : "${WP5_AUDIT_MEMBERSHIP:?Actual fixed audit required}"
  : "${WP5_REPRODUCTION_PACKAGE:?Actual permanent package required}"
  : "${WP5_PRODUCTION_CONTRACT:?Actual production contract required}"
 ;;
esac
case "$STAGE" in
  catalog) COMMAND=("$PY" "$ROOT/scripts/wp5_acceptance_catalog_v2.py" "$@");;
  verify) COMMAND=("$PY" "$ROOT/scripts/wp5_acceptance_verify_v6.py" "$@" --audit-membership "$WP5_AUDIT_MEMBERSHIP" --reproduction-package "$WP5_REPRODUCTION_PACKAGE" --production-contract "$WP5_PRODUCTION_CONTRACT");;
  plan-200) COMMAND=("$PY" "$ROOT/scripts/wp5_acceptance_recompute_v6.py" plan "$@" --runner "$ROOT/scripts/wp5_runner_v10.py" --node-authority "$WP5_NODE_AUTHORITY" --node-scope-plan "$WP5_NODE_SCOPE_PLAN" --audit-membership "$WP5_AUDIT_MEMBERSHIP" --reproduction-package "$WP5_REPRODUCTION_PACKAGE" --production-contract "$WP5_PRODUCTION_CONTRACT");;
  recompute-200) COMMAND=("$PY" "$ROOT/scripts/wp5_acceptance_launch_v3.py" "$@");;
  compare-200) COMMAND=("$PY" "$ROOT/scripts/wp5_acceptance_recompute_v6.py" compare "$@");;
  pilot) COMMAND=("$PY" "$ROOT/scripts/wp5_acceptance_pilot.py" "$@");;
  storage) COMMAND=("$PY" "$ROOT/scripts/wp5_acceptance_storage_v2.py" "$@");;
  delivery) COMMAND=("$PY" "$ROOT/scripts/wp5_acceptance_delivery_v2.py" "$@");;
  *) printf 'Unsupported acceptance stage: %s\n' "$STAGE" >&2;exit 2;;
esac
WP5_ACCEPTANCE_TMP="/tmp/wp5acceptance_${UID}_${SLURM_JOB_ID}"
if [[ -e "$WP5_ACCEPTANCE_TMP" ]];then printf 'Private temp already exists; preserving it\n' >&2;exit 2;fi
mkdir -m 700 -- "$WP5_ACCEPTANCE_TMP"
export TMPDIR="$WP5_ACCEPTANCE_TMP"
cleanup() {
  if [[ "$WP5_ACCEPTANCE_TMP" == "/tmp/wp5acceptance_${UID}_${SLURM_JOB_ID}" && -d "$WP5_ACCEPTANCE_TMP" ]];then
    rm -rf -- "$WP5_ACCEPTANCE_TMP"
  fi
}
trap cleanup EXIT
cd "$WP5_ACCEPTANCE_TMP"
START_EPOCH=$(date +%s)
set +e
if [[ "$STAGE" == recompute-200 ]];then
  # Frozen runner receives --hours46 from its plan and owns QM/deadline handling.
  "${COMMAND[@]}"
else
  # Metadata/verification owns this process group. Stop at46h, before48h Slurm.
  timeout --preserve-status --signal=TERM --kill-after=120s 46h "${COMMAND[@]}"
fi
RC=$?
set -e
"$PY" - "$ROOT" "$STAGE" "$START_EPOCH" "$RC" <<'PY'
import json,os,socket,sys,time
from pathlib import Path
root,stage,started,rc=sys.argv[1:]
path=Path(root)/"acceptance"/("dispatch_"+os.environ["SLURM_JOB_ID"]+".json")
with path.open("x") as stream:
    json.dump({"stage":stage,"job_id":os.environ["SLURM_JOB_ID"],"node":socket.gethostname(),
      "allocated_cpus":int(os.environ["SLURM_CPUS_PER_TASK"]),"internal_metadata_deadline_hours":46,
      "elapsed_seconds":time.time()-int(started),"exit_code":int(rc),"own_temp":os.environ["TMPDIR"],
      "cleanup_on_exit":True,"original_data_written":False},stream,indent=2);stream.write("\n")
PY
exit "$RC"

