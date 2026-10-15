#!/usr/bin/env python3
"""Synthetic WP4 capability probe; never opens or writes LMDB.

Run only in CPU Slurm. Independent single-core workers have private scratch
directories. Synthetic records are not the WP4 retained dataset sample.
"""
from __future__ import annotations
import argparse
import collections
import concurrent.futures
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
THREAD_ENV = {name: "1" for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS")}
EH_TO_EV, BOHR_TO_A = 27.211386245988, 0.529177210903

def write_json(path, value):
    path = Path(path)
    pending = path.with_suffix(path.suffix + ".pending")
    with pending.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
    pending.replace(path)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""): h.update(block)
    return h.hexdigest()

def number(value):
    parsed = float(value.replace("D", "E").replace("d", "e"))
    return parsed if math.isfinite(parsed) else None

def last_float(pattern, text):
    matches = re.findall(pattern, text, flags=re.I | re.M)
    return number(matches[-1]) if matches else None

def aux_data(text):
    """Preserve original AUX field names, units and declared array lengths."""
    result = {}
    matches = list(re.finditer(r"(?m)^\s*([A-Z][A-Z0-9_:./-]*)(?:\[(\d+)\])?\s*=\s*", text))
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw = text[match.end():stop].strip()
        raw = "\n".join(line for line in raw.splitlines() if not line.lstrip().startswith("#"))
        tokens = raw.split()
        count = int(match.group(2)) if match.group(2) is not None else None
        if count is not None: tokens = tokens[:count]
        values = [number(token) if re.fullmatch(FLOAT, token) else token.strip('"') for token in tokens]
        result[match.group(1)] = {"declared_count": count, "values": values, "count_matches": count is None or len(values) == count}
    return result

def section_atom_table(text, marker, symbols, nvalues=1):
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if re.search(marker, line, re.I)]
    for start in reversed(starts):
        rows = []
        for line in lines[start + 1:start + len(symbols) + 15]:
            tokens = line.split()
            if len(tokens) >= nvalues + 2 and tokens[0].isdigit():
                if int(tokens[0]) != len(rows) + 1 or tokens[1] != symbols[len(rows)]: break
                try: row = [number(x) for x in tokens[2:2+nvalues]]
                except ValueError: break
                if None in row: break
                rows.append(row)
                if len(rows) == len(symbols): return rows
            elif rows: break
    return None

def parse_mopac(text, work, symbols):
    aux_path = work / "input.aux"
    aux = aux_data(aux_path.read_text(errors="replace")) if aux_path.exists() else {}
    markers = {
        "gradients": r"FINAL POINT AND DERIVATIVES|GRADIENTS|GRADIENT\s+NORM",
        "bonds": r"BOND ORDERS|BOND-ORDER|BOND ORDER|VALENCIES|VALENCES",
        "mulliken": r"MULLIKEN POPULATION|MULLIKEN.*CHARGE|MULLIKEN ATOMIC",
        "sigma_pi": r"SIGMA.*PI|SIGMA-PI|SIGMA BOND|PI BOND|SIGMA.*BONDS",
        "super": r"SUPERDELOCAL|DELOCALIZABIL|NUCLEOPHILIC.*ELECTROPHILIC",
        "enpart": r"ENERGY PARTITION|ONE-CENTER TERMS|TWO-CENTER TERMS",
        "dispersion": r"DISPERSION ENERGY|HYDROGEN BONDING ENERGY|DISPERSION.*CORRECTION",
        "esp": r"ESP.*CHARGES|ELECTROSTATIC POTENTIAL.*CHARG|ELECTROSTATIC POTENTIAL FIT|ATOM.*ESP CHARGE",
        "cosmo": r"COSMO AREA|COSMO VOLUME|DIELECTRIC ENERGY",
        "polar": r"POLARIZABILITY TENSOR|POLARIZABILITY \(ALPHA\)|POLARIZABILITY.*A\.U\.|ALPHA.*POLARIZABILITY|STATIC POLARIZABILITY",
    }
    present = {name: bool(re.search(pattern, text, re.I)) for name, pattern in markers.items()}
    net = section_atom_table(text, r"NET ATOMIC CHARGES", symbols)
    return {
        "software_version_lines": [x.strip() for x in text.splitlines() if re.search(r"MOPAC v\d", x)],
        "heat_of_formation_kcal_mol": last_float(r"FINAL\s+HEAT\s+OF\s+FORMATION\s*=\s*("+FLOAT+r")\s*KCAL", text),
        "gradient_norm_kcal_mol_A": last_float(r"GRADIENT\s+NORM\s*=\s*("+FLOAT+r")", text),
        "total_energy_eV": last_float(r"\bTOTAL ENERGY\s*=\s*("+FLOAT+r")\s*EV", text),
        "electronic_energy_eV": last_float(r"ELECTRONIC ENERGY\s*=\s*("+FLOAT+r")\s*EV", text),
        "core_core_repulsion_eV": last_float(r"CORE-CORE REPULSION\s*=\s*("+FLOAT+r")\s*EV", text),
        "dielectric_energy_eV": last_float(r"DIELECTRIC ENERGY\s*=\s*("+FLOAT+r")\s*EV", text),
        "cosmo_area_A2": last_float(r"COSMO AREA\s*=\s*("+FLOAT+r")", text),
        "cosmo_volume_A3": last_float(r"COSMO VOLUME\s*=\s*("+FLOAT+r")", text),
        "net_atomic_charges_e": [row[0] for row in net] if net is not None else None,
        "net_charge_sum_e": sum(row[0] for row in net) if net is not None else None,
        "normal_end": "JOB ENDED NORMALLY" in text.upper(),
        "output_sections_present": present, "aux": aux,
    }

def parse_gradient(path, natoms):
    if not path.exists(): return None
    blocks = []
    for line in path.read_text(errors="replace").splitlines():
        tokens = line.split()
        if len(tokens) == 3 and all(re.fullmatch(FLOAT, token) for token in tokens):
            blocks.append([number(x) for x in tokens])
    if len(blocks) < natoms or any(None in row for row in blocks[-natoms:]): return None
    return blocks[-natoms:]

def parse_xtb(text, work, symbols):
    data_path = work / "xtbout.json"
    raw, json_error = None, None
    if data_path.exists():
        try: raw = json.loads(data_path.read_text())
        except (ValueError, OSError) as exc: json_error = str(exc)
    gradient = parse_gradient(work / "gradient", len(symbols))
    charges_path = work / "charges"
    charges = None
    if charges_path.exists():
        try: charges = [number(x) for x in charges_path.read_text().split()]
        except ValueError: pass
    freq, intensity = [], []
    spectrum = work / "vibspectrum"
    if spectrum.exists():
        for line in spectrum.read_text(errors="replace").splitlines():
            t = line.split()
            if len(t) >= 4 and t[0].isdigit():
                try: freq.append(number(t[2])); intensity.append(number(t[3]))
                except ValueError: pass
    return {
        "software_version_lines": [x.strip() for x in text.splitlines() if re.search(r"xtb version", x, re.I)],
        "total_energy_Eh": last_float(r"\bTOTAL ENERGY\s+("+FLOAT+r")\s*Eh", text),
        "gradient_norm_Eh_bohr": last_float(r"\bGRADIENT NORM\s+("+FLOAT+r")", text),
        "homo_eV": last_float(r"HOMO orbital eigv\.\s+("+FLOAT+r")", text),
        "lumo_eV": last_float(r"LUMO orbital eigv\.\s+("+FLOAT+r")", text),
        "Gsolv_Eh": last_float(r"->\s*Gsolv\s+("+FLOAT+r")", text),
        "vertical_IP_eV": last_float(r"delta SCC IP \(eV\):\s*("+FLOAT+r")", text),
        "vertical_EA_eV": last_float(r"delta SCC EA \(eV\):\s*("+FLOAT+r")", text),
        "NFOD_e": last_float(r"NFOD\s*:\s*("+FLOAT+r")", text),
        "zero_point_energy_Eh": last_float(r"zero point energy\s+("+FLOAT+r")", text),
        "atomic_charges_e": charges,
        "charge_count_matches": charges is not None and len(charges) == len(symbols),
        "gradient_Eh_bohr": gradient,
        "forces_eV_A": [[-x*EH_TO_EV/BOHR_TO_A for x in row] for row in gradient] if gradient else None,
        "frequencies_cm_inverse": freq, "IR_intensities_printed": intensity,
        "imaginary_frequency_count_raw": sum(x < 0 for x in freq if x is not None),
        "imaginary_frequency_count_below_minus20": sum(x < -20 for x in freq if x is not None),
        "scc_convergence_markers": re.findall(r".*(?:converged|SCC.*fail|SCC.*not converg).*", text, re.I)[-20:],
        "normal_end": "normal termination of xtb" in text.lower(),
        "xtbout_json": raw, "json_parse_error": json_error,
        "output_sections_present": {
            "fukui": bool(re.search(r"f\(\+\).*f\(-\)|f\(\+\).*f\(0\)", text)),
            "dipole": "molecular dipole:" in text.lower(),
            "quadrupole": "molecular quadrupole" in text.lower(),
            "dispersion_coefficients": "C6AA" in text,
            "thermodynamics": "Thermodynamic Functions" in text,
        },
    }

def owned_cleanup(root):
    """Validate exact private scratch tree ownership/type before removal."""
    root = Path(root)
    if root.parent != Path(tempfile.gettempdir()) or not root.name.startswith("wp4probe_"):
        raise RuntimeError("Unexpected scratch root: "+str(root))
    entries = [root, *root.rglob("*")]
    for path in entries:
        info = path.lstat()
        if info.st_uid != os.getuid() or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise RuntimeError("Scratch ownership/type differs: "+str(path))
    total = sum(p.lstat().st_size for p in entries if p.is_file())
    shutil.rmtree(root)
    return total

def limits():
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 << 20, 32 << 20))

def invoke(task, symbols, coords, out, config):
    out.mkdir(parents=True, exist_ok=False)
    scratch = Path(tempfile.mkdtemp(prefix=f"wp4probe_{os.getuid()}_{os.environ['SLURM_JOB_ID']}_"))
    env = {**os.environ, **THREAD_ENV, "CUDA_VISIBLE_DEVICES": "", "TMPDIR": str(scratch), "TMP": str(scratch)}
    family = task["family"]
    env.update(config.get(family+"_environment", {}))
    stdout_path = scratch / "process.out"
    result = {"task": task["name"], "family": family, "keywords": task.get("keywords"),
              "requested_properties": task.get("required", []), "scratch": str(scratch), "hostname": os.uname().nodename}
    started = time.monotonic()
    try:
        xyz = str(len(symbols))+"\nSynthetic capability probe; coordinates Angstrom\n"
        xyz += "\n".join(f"{s} {x:.10f} {y:.10f} {z:.10f}" for s,(x,y,z) in zip(symbols,coords))+"\n"
        (scratch / "input.xyz").write_text(xyz)
        executable = config.get(family+"_executable")
        if not executable or not Path(executable).is_file() or not os.access(executable, os.X_OK):
            result.update(status="EXECUTABLE_UNAVAILABLE", failure_reason=str(executable))
            return result
        if family == "mopac":
            result["keywords"] = task["keywords"]+" THREADS=1"
            mop = result["keywords"]+"\nSynthetic capability probe\nCartesian Angstrom; 1SCF fixed geometry\n"
            mop += "\n".join(f"{s} {x:.10f} 1 {y:.10f} 1 {z:.10f} 1" for s,(x,y,z) in zip(symbols,coords))+"\n"
            (scratch / "input.mop").write_text(mop)
            argv = [executable, "input.mop"]
        else:
            (scratch / "probe.inp").write_text(task.get("xcontrol", "$write\n json=true\n$end\n"))
            argv = [executable, "input.xyz", "--input", "probe.inp", "--norestart", "--parallel", "1", *task["args"]]
        result["argv"] = argv
        with stdout_path.open("wb") as handle:
            process = subprocess.Popen(argv, cwd=scratch, env=env, stdout=handle, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, start_new_session=True, preexec_fn=limits)
            try:
                returncode = process.wait(timeout=task.get("timeout_seconds", config["timeout_seconds"]))
                result["timeout"] = False
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); returncode = process.wait()
                result["timeout"] = True
        result["returncode"] = returncode
        text = (scratch / "input.out" if family == "mopac" and (scratch / "input.out").exists() else stdout_path).read_text(errors="replace")
        result["parsed"] = parse_mopac(text, scratch, symbols) if family == "mopac" else parse_xtb(text, scratch, symbols)
        combined = text + "\n" + stdout_path.read_text(errors="replace")
        result["diagnostic_lines"] = [line.strip() for line in combined.splitlines()
            if re.search(r"error|failed|not allowed|not available|does not work|cannot|warning|unrecognized|not converg|fragile|abnormal", line, re.I)][-40:]
        fatal = bool(re.search(r"MULLIKEN POPULATION NOT AVAILABLE|POLAR does not work|SCF DOES NOT CONVERGE|SCF FAILED|GEOMETRY IN ERROR|UNRECOGNIZED KEY|Unknown option|abnormal termination", combined, re.I))
        success = returncode == 0 and result["parsed"]["normal_end"] and not result["timeout"] and not fatal
        result["status"] = "PROCESS_SUCCESS" if success else "TIMEOUT" if result["timeout"] else "CALCULATION_FAILED"
        result["failure_reason"] = None if success else " | ".join(result["diagnostic_lines"]) or f"exit={returncode}; normal_end={result['parsed']['normal_end']}"
        missing = [key for key in task.get("required", []) if not result["parsed"]["output_sections_present"].get(key, False)]
        result["missing_output_markers"] = missing
        result["property_check"] = "MARKERS_PRESENT_REQUIRES_VALUE_PARSER" if success and not missing else "OUTPUT_MARKERS_MISSING" if success else "CALCULATION_FAILED"
        files = []
        for path in sorted(scratch.iterdir()):
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                files.append({"name": path.name, "retained": False, "type": "not_owned_regular"}); continue
            retained = (path.suffix in (".out", ".mop", ".aux", ".json", ".inp", ".xyz") or path.name in ("gradient", "charges", "wbo", "fod", "vibspectrum")) and info.st_size <= (8 << 20)
            files.append({"name": path.name, "bytes": info.st_size, "sha256": sha(path), "retained": retained})
            if retained: shutil.copyfile(path, out / path.name)
        result["files"] = files
        result["raw_total_bytes"] = sum(item.get("bytes", 0) for item in files)
        result["retained_bytes"] = sum(item.get("bytes", 0) for item in files if item["retained"])
        return result
    except Exception as exc:
        result.update(status="RUNNER_ERROR", failure_reason=f"{type(exc).__name__}: {exc}")
        return result
    finally:
        result["elapsed_seconds"] = time.monotonic() - started
        try:
            result["scratch_bytes_removed"] = owned_cleanup(scratch)
            result["scratch_cleanup"] = "REMOVED_OWNED_PRIVATE_TREE"
        except Exception as exc:
            result["scratch_cleanup"] = f"PRESERVED: {type(exc).__name__}: {exc}"
        write_json(out / "result.json", result)

def molecule_worker(spec, config, output):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    import numpy as np
    destination = Path(output) / spec["name"]; destination.mkdir()
    molecule = Chem.AddHs(Chem.MolFromSmiles(spec["smiles"]))
    params = AllChem.ETKDGv3(); params.randomSeed = config["seed"] + spec["ordinal"]; params.numThreads = 1
    embed = AllChem.EmbedMolecule(molecule, params)
    if embed != 0: raise RuntimeError("Synthetic embed failed: "+spec["name"])
    mmff = AllChem.MMFFOptimizeMolecule(molecule, maxIters=1000) if AllChem.MMFFHasAllMoleculeParams(molecule) else None
    symbols = [atom.GetSymbol() for atom in molecule.GetAtoms()]
    coords = molecule.GetConformer().GetPositions()
    rng = np.random.default_rng(config["seed"] + spec["ordinal"])
    perturbed = coords + rng.normal(0, config["perturb_sigma_A"], coords.shape)
    write_json(destination / "synthetic_geometry.json", {**spec, "atoms": symbols, "positions_A": coords.tolist(),
        "perturbed_positions_A": perturbed.tolist(), "MMFF_returncode": mmff,
        "geometry_source": "RDKit ETKDGv3 synthetic; not native PM7 geometry", "seed": config["seed"]+spec["ordinal"]})
    results = []
    for task in config["tasks"]:
        result = invoke(task, symbols, perturbed if task.get("perturbed") else coords, destination / task["name"], config)
        result.update(molecule=spec["name"], smiles=spec["smiles"], natoms=len(symbols), worker_pid=os.getpid())
        write_json(destination / task["name"] / "result.json", result); results.append(result)
    return results

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True); parser.add_argument("--output")
    parser.add_argument("--workers", type=int, default=16); parser.add_argument("--xtb-executable")
    parser.add_argument("--check", action="store_true", help="Check configuration/parser fixtures without chemistry")
    parser.add_argument("--families", default="mopac,xtb"); args = parser.parse_args()
    if args.check:
        config = json.loads(Path(args.config).read_text())
        assert len(config["molecules"]) >= 16
        assert len({task["name"] for task in config["tasks"]}) == len(config["tasks"])
        assert all("1SCF" in task["keywords"] for task in config["tasks"] if task["family"] == "mopac")
        example = aux_data("HEAT_OF_FORMATION:KCAL/MOL=-12.5\nATOM_CHARGES[0003]=\n -0.4 0.2 0.2\nGRADIENTS:KCAL/MOL/ANGSTROM[0003]=\n 1D-2 2D-2 3D-2\n")
        assert example["ATOM_CHARGES"]["values"] == [-0.4, 0.2, 0.2]
        assert example["GRADIENTS:KCAL/MOL/ANGSTROM"]["count_matches"]
        assert example["GRADIENTS:KCAL/MOL/ANGSTROM"]["values"] == [0.01, 0.02, 0.03]
        assert section_atom_table("NET ATOMIC CHARGES\n ATOM NO. TYPE CHARGE\n 1 O -0.4\n 2 H 0.2\n 3 H 0.2\n", "NET ATOMIC CHARGES", ["O", "H", "H"]) == [[-0.4], [0.2], [0.2]]
        print(json.dumps({"status": "STATIC_AND_PARSER_FIXTURES_PASS", "molecules": len(config["molecules"]),
                          "tasks": len(config["tasks"]), "chemistry_executed": False}))
        return 0
    if not args.output: parser.error("--output required for capability run")
    if not os.environ.get("SLURM_JOB_ID"): raise SystemExit("Requires CPU Slurm allocation")
    allocated = int(os.environ.get("SLURM_CPUS_PER_TASK", "0"))
    if allocated < 16 or args.workers < 16 or args.workers > allocated:
        raise SystemExit("Requires >=16 allocated CPUs and effective workers <= allocation")
    os.environ.update(THREAD_ENV)
    config = json.loads(Path(args.config).read_text())
    if args.xtb_executable: config["xtb_executable"] = args.xtb_executable
    families = set(args.families.split(","))
    config["tasks"] = [task for task in config["tasks"] if task["family"] in families]
    output = Path(args.output).absolute(); output.mkdir(parents=True, exist_ok=False)
    metadata = {"scope": "SYNTHETIC_CAPABILITY_PROBE_NOT_WP4_RETAINED_SAMPLE", "seed": config["seed"],
        "job_id": os.environ["SLURM_JOB_ID"], "hostname": os.uname().nodename, "allocated_cpus": allocated,
        "workers": args.workers, "threads_per_worker": 1, "python_logical_entry": sys.executable,
        "source_sha256": sha(__file__), "config_sha256": sha(args.config),
        "software_packages": {x: importlib.metadata.version(x) for x in ("rdkit", "numpy")}, "config": config}
    write_json(output / "metadata.json", metadata)
    started = time.monotonic(); results, errors = [], []
    with (output / "progress.jsonl").open("w") as progress:
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            jobs = {pool.submit(molecule_worker, {**spec, "ordinal": index}, config, str(output)): spec["name"]
                    for index, spec in enumerate(config["molecules"])}
            for future in concurrent.futures.as_completed(jobs):
                try:
                    rows = future.result(); results.extend(rows)
                    note = {"molecule": jobs[future], "calculations": len(rows), "statuses": dict(collections.Counter(row["status"] for row in rows))}
                except Exception as exc:
                    note = {"molecule": jobs[future], "error": f"{type(exc).__name__}: {exc}"}; errors.append(note)
                progress.write(json.dumps(note)+"\n"); progress.flush(); os.fsync(progress.fileno())
                print(json.dumps(note), flush=True)
    aggregates = {}
    for task in config["tasks"]:
        rows = [r for r in results if r["task"] == task["name"]]; times = sorted(r["elapsed_seconds"] for r in rows)
        aggregates[task["name"]] = {"n": len(rows), "statuses": dict(collections.Counter(r["status"] for r in rows)),
            "property_checks": dict(collections.Counter(r.get("property_check", "NOT_CHECKED") for r in rows)),
            "seconds_min": min(times) if times else None, "seconds_median": times[len(times)//2] if times else None,
            "seconds_max": max(times) if times else None, "raw_total_bytes": sum(r.get("raw_total_bytes",0) for r in rows),
            "failure_reasons": dict(collections.Counter(r["failure_reason"] for r in rows if r.get("failure_reason"))),
            "missing_markers": dict(collections.Counter(x for r in rows for x in r.get("missing_output_markers",[])))}
    write_json(output / "summary.json", {"scope": metadata["scope"], "elapsed_seconds": time.monotonic()-started,
        "planned_molecules": len(config["molecules"]), "calculations": len(results), "molecule_errors": errors,
        "tasks": aggregates, "worker_pids": sorted(set(r["worker_pid"] for r in results)),
        "scratch_cleanup_failures": [r["scratch"] for r in results if not r["scratch_cleanup"].startswith("REMOVED")]})
    return 2 if errors or any(r["status"] == "RUNNER_ERROR" for r in results) else 0

if __name__ == "__main__":
    raise SystemExit(main())
