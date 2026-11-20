"""Move the one closed D diagnostic cache to its allocated CPU node.

Reuse rsync and the existing owned-process guard. No source dataset, hashes,
scientific values, manifest paths or other output trees are changed/deleted.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess

from .resources import DJointGuard, execution_site, local_scope


def transfer(configuration, *, guard=None, run=subprocess.run):
    execution_site(configuration, cpu=True)
    if configuration["source_node"] not in {"compute-0-" + str(i) for i in (*range(8), 20, 22)}:
        raise ValueError("Use an allowed GPU node as the diagnostic source")
    scope = local_scope(configuration)
    output = Path(configuration["output"]).resolve()
    guard = DJointGuard(configuration) if guard is None else guard
    guard.check(output)
    manifest = output / "manifest.json"
    if manifest.is_file():
        previous = json.loads(manifest.read_text())
        if previous.get("binding") != configuration["forward_binding"]:
            raise ValueError("Destination contains a different diagnostic condition; preserve it")
    code = "import json,sys; x=json.load(open(sys.argv[1])); print(json.dumps({'schema':x.get('schema'),'status':x.get('status'),'binding':x.get('binding')}))"
    command = shlex.join(["/usr/bin/python3", "-B", "-c", code, str(manifest)])
    observed = run(["ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                    configuration["source_node"], command], check=True, capture_output=True, text=True)
    closed = json.loads(observed.stdout)
    if (closed.get("schema") != "D_REPRESENTATION_FORWARD_V1"
            or closed.get("status") != "FORWARD_COMPLETE"
            or closed.get("binding") != configuration["forward_binding"]):
        raise ValueError("Wait for the same registered diagnostic forward to close")
    guard.check(scope)
    scope.mkdir(parents=True, exist_ok=True)
    # ssh -n is for the metadata command only. rsync requires its transport's
    # stdin, and --partial preserves this task's incomplete cache on failure.
    guard.run(["rsync", "-a", "--sparse", "--partial", "--protect-args", "-e",
               "ssh -o BatchMode=yes -o ConnectTimeout=10",
               configuration["source_node"] + ":" + str(scope) + "/", str(scope) + "/"], output)
    return dict(status="CACHE_TRANSFER_COMPLETE", source_node=configuration["source_node"],
                destination_node=configuration["local_node"], source_scope=str(scope),
                output=str(output), scientific_values_changed=False, original_sources_copied=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    args = parser.parse_args()
    result = transfer(json.loads(Path(args.configuration).read_text()))
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
