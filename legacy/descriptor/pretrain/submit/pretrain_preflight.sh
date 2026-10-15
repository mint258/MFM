#!/usr/bin/env bash

set -euo pipefail

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

section() {
  echo
  echo "========== $* =========="
}

check_required_python_modules() {
  "${PYTHON_BIN}" - <<'PY'
import importlib

mods = ["torch", "torch_geometric", "lmdb", "rdkit", "wandb", "numpy", "sklearn", "tqdm", "periodictable"]
missing = []
for name in mods:
    try:
        importlib.import_module(name)
    except Exception as exc:
        missing.append((name, repr(exc)))

if missing:
    print("required_python_modules_status=missing")
    for name, exc in missing:
        print(f"missing_module={name} error={exc}")
    raise SystemExit(1)

print("required_python_modules_status=ok")
PY
}

REPO_ROOT="${REPO_ROOT:?REPO_ROOT is required}"
VARIANT_ROOT="${VARIANT_ROOT:?VARIANT_ROOT is required}"
VARIANT_MODULE_PREFIX="${VARIANT_MODULE_PREFIX:-}"
PYTHON_BIN="${PYTHON_BIN:-python}"
DATA_ROOT="${DATA_ROOT:-}"
DATA_ROOTS="${DATA_ROOTS:-}"
DDP_NPROC_PER_NODE="${DDP_NPROC_PER_NODE:-4}"
ENV_SMOKE_TRAIN_START="${ENV_SMOKE_TRAIN_START:-0}"
ENV_SMOKE_TRAIN_END="${ENV_SMOKE_TRAIN_END:-3}"
RUN_ENV_SMOKE="${RUN_ENV_SMOKE:-1}"
RUN_ALLREDUCE_PREFLIGHT="${RUN_ALLREDUCE_PREFLIGHT:-1}"
ALLREDUCE_TENSOR_MB="${ALLREDUCE_TENSOR_MB:-256}"
ALLREDUCE_WARMUP_ITERS="${ALLREDUCE_WARMUP_ITERS:-10}"
ALLREDUCE_ITERS="${ALLREDUCE_ITERS:-30}"
ALLREDUCE_DTYPE="${ALLREDUCE_DTYPE:-bfloat16}"

if [[ -z "${DATA_ROOT}" ]]; then
  if [[ -n "${DATA_ROOTS}" ]]; then
    read -r -a DATA_ROOT_ARR <<< "${DATA_ROOTS}"
    DATA_ROOT="${DATA_ROOT_ARR[0]:-}"
  fi
fi

if [[ -z "${DATA_ROOT}" ]]; then
  echo "DATA_ROOT or DATA_ROOTS is required for preflight." >&2
  exit 1
fi

section "Preflight Context"
echo "[$(timestamp)] repo_root=${REPO_ROOT}"
echo "[$(timestamp)] variant_root=${VARIANT_ROOT}"
echo "[$(timestamp)] variant_module_prefix=${VARIANT_MODULE_PREFIX}"
echo "[$(timestamp)] python_bin=${PYTHON_BIN}"
echo "[$(timestamp)] data_root=${DATA_ROOT}"
echo "[$(timestamp)] data_roots=${DATA_ROOTS:-${DATA_ROOT}}"
echo "[$(timestamp)] ddp_nproc_per_node=${DDP_NPROC_PER_NODE}"
echo "[$(timestamp)] run_env_smoke=${RUN_ENV_SMOKE}"
echo "[$(timestamp)] run_allreduce_preflight=${RUN_ALLREDUCE_PREFLIGHT}"

if [[ ! -e "${DATA_ROOT}" ]]; then
  echo "[$(timestamp)] ERROR: DATA_ROOT does not exist: ${DATA_ROOT}" >&2
  exit 1
fi

if [[ -n "${DATA_ROOTS}" ]]; then
  read -r -a DATA_ROOT_ARR <<< "${DATA_ROOTS}"
  for root_path in "${DATA_ROOT_ARR[@]}"; do
    if [[ ! -e "${root_path}" ]]; then
      echo "[$(timestamp)] ERROR: one DATA_ROOTS entry does not exist: ${root_path}" >&2
      exit 1
    fi
  done
fi

section "Slurm And System"
scontrol show job "${SLURM_JOB_ID:-}" || true
scontrol show node "${SLURMD_NODENAME:-$(hostname)}" || true
ulimit -a || true

section "GPU Topology"
nvidia-smi -L || true
nvidia-smi topo -m || true
nvidia-smi || true
echo "[$(timestamp)] CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-unset}"

section "Python Environment"
which "${PYTHON_BIN}" || true
"${PYTHON_BIN}" --version
"${PYTHON_BIN}" - <<'PY'
import importlib
import platform
import sys

mods = ["torch", "torch_geometric", "lmdb", "rdkit", "wandb", "numpy", "sklearn", "tqdm", "periodictable"]
print("python_executable=", sys.executable)
print("python_version=", sys.version.replace("\n", " "))
print("platform=", platform.platform())
for name in mods:
    try:
        module = importlib.import_module(name)
        print(f"{name}_version=", getattr(module, "__version__", "unknown"))
    except Exception as exc:
        print(f"{name}_import_error=", repr(exc))
PY

if ! check_required_python_modules; then
  section "Dependency Failure"
  echo "[$(timestamp)] ERROR: current Python environment is missing required dependencies." >&2
  exit 1
fi

section "CUDA And Distributed Sanity"
"${PYTHON_BIN}" - <<'PY'
import torch
import torch.distributed as dist

print("torch_version=", torch.__version__)
print("cuda_available=", torch.cuda.is_available())
print("cuda_device_count=", torch.cuda.device_count())
print("distributed_available=", dist.is_available())
print("nccl_available=", dist.is_nccl_available() if dist.is_available() else False)
print("gloo_available=", dist.is_gloo_available() if dist.is_available() else False)
for idx in range(torch.cuda.device_count()):
    props = torch.cuda.get_device_properties(idx)
    print(
        f"gpu[{idx}] name={props.name} total_memory_gb={props.total_memory / (1024 ** 3):.2f} "
        f"sm_count={props.multi_processor_count}"
    )
PY

TORCHRUN_CMD=("${PYTHON_BIN}" -m torch.distributed.run --standalone --nproc_per_node="${DDP_NPROC_PER_NODE}")

if [[ "${RUN_ENV_SMOKE}" == "1" ]]; then
  section "Env Smoke"
  ENV_SMOKE_OK=0
  if [[ -n "${DATA_ROOTS}" ]]; then
    read -r -a ENV_SMOKE_ROOTS <<< "${DATA_ROOTS}"
  else
    ENV_SMOKE_ROOTS=("${DATA_ROOT}")
  fi

  for candidate_root in "${ENV_SMOKE_ROOTS[@]}"; do
    echo "[$(timestamp)] env_smoke_candidate=${candidate_root}"
    if CUDA_VISIBLE_DEVICES=0 "${PYTHON_BIN}" "${VARIANT_ROOT}/pretrain/submit/env_smoke_check.py" \
      --data-root "${candidate_root}" \
      --train-start "${ENV_SMOKE_TRAIN_START}" \
      --train-end "${ENV_SMOKE_TRAIN_END}" \
      --batch-size 2 \
      --device auto; then
      ENV_SMOKE_OK=1
      DATA_ROOT="${candidate_root}"
      echo "[$(timestamp)] env_smoke_selected=${candidate_root}"
      break
    fi
    echo "[$(timestamp)] WARNING: env smoke failed for shard ${candidate_root}; trying next shard."
  done

  if [[ "${ENV_SMOKE_OK}" != "1" ]]; then
    echo "[$(timestamp)] ERROR: env smoke failed for all candidate dataset roots." >&2
    exit 1
  fi
fi

if [[ "${RUN_ALLREDUCE_PREFLIGHT}" == "1" ]]; then
  section "Allreduce Preflight"
  "${TORCHRUN_CMD[@]}" "${VARIANT_ROOT}/pretrain/submit/ddp_allreduce_smoke.py" \
    --backend nccl \
    --tensor-mb "${ALLREDUCE_TENSOR_MB}" \
    --warmup-iters "${ALLREDUCE_WARMUP_ITERS}" \
    --iters "${ALLREDUCE_ITERS}" \
    --dtype "${ALLREDUCE_DTYPE}"
fi

section "Preflight Finished"
echo "[$(timestamp)] Preflight checks passed."
