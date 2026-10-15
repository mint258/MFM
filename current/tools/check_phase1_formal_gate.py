#!/usr/bin/env python3
"""Read-only formal preflight; exported JSON/text alone never yields a PASS."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phychem_mfm.phase1.formal_gate import check_formal_gate


def _object(path: str):
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, help="Existing independently reviewed frozen JSON; never created by this tool")
    parser.add_argument("--slurm-config", required=True, help="Read-only exported scontrol show config text")
    parser.add_argument("--slurm-node", required=True, help="Read-only exported scontrol show node text for exactly one node")
    parser.add_argument("--slurm-job", help="Current allocation's exported scontrol show job text; required for live pass")
    parser.add_argument("--configuration-node", help="Node identified by the standard configuration export")
    parser.add_argument("--gres-config", help="Existing standard gres.conf, or exported slurmd -G device mappings")
    parser.add_argument("--cgroup-config", help="Existing standard cgroup.conf")
    parser.add_argument("--sshd-config", help="Existing standard sshd_config; reads ordinary Include dependencies")
    parser.add_argument("--ssh-pam-config", help="Existing standard PAM sshd file; reads ordinary include dependencies")
    parser.add_argument("--artifact", action="append", default=[], metavar="DOTTED_FIELD=LOCAL_PATH",
                        help="Exact frozen protocol/proof file; may be repeated. Only reads and hashes the named file")
    parser.add_argument("--live-allocation", action="store_true",
                        help="Additionally inspect this Linux Slurm allocation using local env/cgroup/NVIDIA/device access; no connections")
    args = parser.parse_args(argv)
    try:
        artifacts = {}
        for item in args.artifact:
            key, separator, path = item.partition("=")
            if not separator or not key or not path or key in artifacts:
                raise ValueError("Each unique --artifact must be DOTTED_FIELD=LOCAL_PATH")
            artifacts[key] = path
        report = check_formal_gate(
            _object(args.protocol),
            slurm_config_text=Path(args.slurm_config).read_text(encoding="utf-8"),
            slurm_node_text=Path(args.slurm_node).read_text(encoding="utf-8"),
            slurm_job_text=Path(args.slurm_job).read_text(encoding="utf-8") if args.slurm_job else "",
            configuration_files={"gres": args.gres_config, "cgroup": args.cgroup_config,
                                 "sshd": args.sshd_config, "pam": args.ssh_pam_config},
            configuration_node=args.configuration_node,
            artifacts=artifacts, live_allocation=args.live_allocation,
        )
    except (OSError, TypeError, ValueError) as error:
        print(json.dumps({"status": "BLOCKED", "may_start_formal_training": False,
                          "issues": [{"code": "input.unverified", "message": str(error)}]}, ensure_ascii=False))
        return 2
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False, allow_nan=False))
    # REVIEW_ONLY cannot be accidentally treated as a successful launch gate.
    return 0 if report.may_start_formal_training else 2


if __name__ == "__main__":
    raise SystemExit(main())
