"""Stage-0 runtime preparation; execute only on allocated CPU nodes."""
import importlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    if (not os.environ.get("SLURM_JOB_ID") or not platform.node().startswith("compute-")
            or not 8 <= int(platform.node().rsplit("-", 1)[-1]) <= 19):
        raise RuntimeError("Allocated CPU node required")
    report = {"node": platform.node(), "job_id": os.environ["SLURM_JOB_ID"],
              "python": sys.executable, "modules": {}}
    for name in ("numpy", "rdkit", "mordred", "pyarrow", "lmdb", "torch"):
        try:
            module = importlib.import_module(name)
            report["modules"][name] = {"path": module.__file__, "version": str(getattr(module, "__version__", "unknown"))}
        except ImportError as error:
            report["modules"][name] = {"unavailable": str(error)}
    for path in ("/", "/tmp", "/share/home/zixiao/descriptor_analysis", "/lfshome/zixiao"):
        report[path] = {"disk": shutil.disk_usage(path)._asdict()}
        for command in (["findmnt", "-T", path], ["df", "-Pi", path]):
            result = subprocess.run(command, capture_output=True, text=True)
            report[path][command[0]] = result.stdout.strip()
    from workflows.data_v1_final.export.v31_stream_v1.quota_snapshot import read_available
    report["actual_share_quota_available_bytes"] = read_available(
        "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json",
        expected_uid=os.getuid(), expected_filesystem="/share", max_age_seconds=5)
    for command in (["quota", "-s"],):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=8)
            report[" ".join(command)] = {"returncode": result.returncode, "output": result.stdout, "error": result.stderr}
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            report[" ".join(command)] = {"unavailable": str(error)}
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
