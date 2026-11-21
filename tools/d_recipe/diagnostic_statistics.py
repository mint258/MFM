"""CPU-only completion of the one registered D representation forward cache."""
import argparse
import json
from pathlib import Path

import numpy as np

from .diagnostics import bootstrap_participation, describe, existing_statistics


def run(configuration, *, guard=None):
    from .resources import execution_site
    execution_site(configuration, cpu=True)
    if guard is None:
        from .resources import DJointGuard
        guard = DJointGuard(configuration)
    output = Path(configuration["output"])
    guard.check(output)
    manifest = json.loads(Path(configuration["forward_manifest"]).read_text())
    if manifest["schema"] != "D_REPRESENTATION_FORWARD_V1" or manifest["status"] != "FORWARD_COMPLETE":
        raise ValueError("A closed D diagnostic forward is required")
    from .diagnostic_forward import registered_endpoint
    registered_endpoint(manifest["binding"] | {"adopted_arm": configuration.get("adopted_arm")})
    summary_path = output / "summary.json"
    if summary_path.exists():
        result = json.loads(summary_path.read_text())
        if result.get("status") != "COMPLETE":
            raise ValueError("The diagnostic summary is not closed")
        if result["binding"] != manifest["binding"]:
            raise ValueError("Diagnostic statistics belong to another endpoint")
        return result
    # Execution-only block size; the closed same-condition summary above is
    # reusable independently of how atom moments were accumulated.
    molecule_chunk = configuration.get("participation_molecule_chunk", 32)
    if type(molecule_chunk) is not int or molecule_chunk < 1:
        raise ValueError("participation_molecule_chunk must be a positive integer")
    with np.load(manifest["panel"]) as archive:
        panel = {name: archive[name] for name in archive.files}
    means = np.load(manifest["means"], mmap_mode="r")
    atoms = np.load(manifest["first_atoms"], mmap_mode="r")
    statistics = existing_statistics()
    weights = np.vstack([np.ones((1, len(panel["first"]))),
                         statistics.bootstrap_weights(len(panel["first"]))])
    def check():
        guard.check(output)
    # Stream atom moments once for the point spectra. All uncertainty below
    # uses the same already generated molecule weights as CEV/CVF.
    layers = {}
    for layer, label in enumerate(manifest["layers"]):
        check()
        total, outer = np.zeros(atoms.shape[-1]), np.zeros((atoms.shape[-1], atoms.shape[-1]))
        for start in range(0, len(atoms), 4096):
            check()
            h = np.asarray(atoms[start:start + 4096, layer], np.float64)
            total += h.sum(0)
            outer += h.T @ h
        layers[str(label)] = dict(means=means[:, layer], first_atom_moments=dict(
            count=len(atoms), total=total, outer=outer))
    result, draws = describe(layers, owners=panel["owners"], first=panel["first"],
        composition=panel["composition"], statistics=statistics, guard=check, weights=weights)
    for layer, label in enumerate(manifest["layers"]):
        atom_pr = bootstrap_participation(atoms[:, layer], panel["atom_ptr"], weights,
            guard=check, molecule_chunk=molecule_chunk)
        first_means = means[panel["first"], layer]
        mean_pr = bootstrap_participation(first_means, np.arange(len(first_means) + 1), weights,
            guard=check, molecule_chunk=molecule_chunk)
        for name, values in (("atom_PR", atom_pr), ("mean_PR", mean_pr)):
            result["layers"][str(label)][name].update(
                bootstrap=True, bootstrap_summary=statistics.summary(values))
            draws[str(label) + "_" + name] = values
    result.update(schema="D_REPRESENTATION_STATISTICS_V1", status="COMPLETE",
        binding=manifest["binding"], forward_manifest=configuration["forward_manifest"],
        PR_uncertainty="1000 paired molecule bootstrap draws, same weights as CEV/CVF",
        participation_molecule_chunk=molecule_chunk,
        bootstrap_draws=str(output / "bootstrap.npz"))
    check()
    output.mkdir(parents=True, exist_ok=True)
    temporary_draws = output / "bootstrap.partial.npz"
    np.savez_compressed(temporary_draws, **draws)
    temporary_draws.replace(output / "bootstrap.npz")
    temporary = summary_path.with_suffix(".partial")
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    temporary.replace(summary_path)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(json.loads(Path(arguments.configuration).read_text()))))
