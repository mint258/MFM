---
name: mfm-hpc-workflow
description: Apply MFM server execution, Slurm, GPU ownership, checkpoint recovery, experiment tracking and storage rules when operating remote compute environments.
metadata:
  version: "1.0.0"
  updated: "2026-11-05"
  derived-from: huagong_hpc_requirement-1.0.145
---

# MFM HPC workflow

Read [working methods](../../../docs/project_context/WORKING_METHOD.md) for the
operation being performed and [scoped decisions](../../../docs/project_context/DECISIONS.md)
for model-v3, the v1 pilot, P′ or PubChem expansion.

- Resolve endpoint identity, project roots, logical Python environment and
  scheduler settings from the current environment. Hostnames/node names are not
  globally unique. Use secure credentials and verify host keys.
- Keep substantial computation inside its actual allocation. One task owner
  coordinates submissions and deduplicates jobs. A CPU allocation without
  registered GPU resources does not reserve a GPU.
- Preserve recipe, geometry/source identity, seed, masks and immutable active
  source. Repair tooling in a separate revision and reuse closed checkpoints.
- Before signaling an owned process, bind UID, PID, boot ID, kernel start ticks,
  command and task/job membership. Never terminate processes by a broad name.
- Budget actual account quota, inode capacity and concurrent future output for
  each storage domain. Whole-filesystem free space is not user quota.
- Distinguish submission, running, partial success, scientific acceptance, model
  acceptance, archive completion and online synchronization.

Do not carry historical PIDs, locks, drive mappings, one-off deletion permissions
or old server-availability observations into a new environment.

