"""Numerical WP4 parsers. Missing properties stay explicit; no marker-only pass."""
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
import sys

FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
EH_TO_EV, BOHR_TO_A = 27.211386245988, 0.529177210903
AU_DIPOLE_TO_DEBYE = 2.541746473

def f(value):
    x = float(value.replace("D", "E").replace("d", "e"))
    if not math.isfinite(x): raise ValueError("Nonfinite numerical output")
    return x

def scalar(text, pattern, last=True):
    hits = re.findall(pattern, text, re.I | re.M)
    return f(hits[-1 if last else 0]) if hits else None

def read_aux(path):
    if not Path(path).exists(): return {}, ["AUX_MISSING"]
    text = Path(path).read_text(errors="replace")
    hits = list(re.finditer(r"(?m)^[ \t]*([A-Z][A-Z0-9_:./ -]*?)(?:\[(\d+)\])?[ \t]*=[ \t]*", text))
    arrays, errors = {}, []
    for i, hit in enumerate(hits):
        name = hit.group(1).strip()
        body = text[hit.end():hits[i+1].start() if i+1<len(hits) else len(text)]
        body = "\n".join(x for x in body.splitlines() if not x.lstrip().startswith("#"))
        tokens = body.strip().split()
        count = int(hit.group(2)) if hit.group(2) else None
        if count is None:
            first = body.strip().splitlines()[0] if body.strip() else ""
            arrays[name] = f(first) if re.fullmatch(FLOAT, first) else first.strip('"')
        else:
            tokens = tokens[:count]
            if len(tokens) != count: errors.append("AUX_COUNT_MISMATCH:"+name)
            arrays[name] = [f(x) if re.fullmatch(FLOAT,x) else x.strip('"') for x in tokens]
    return arrays, errors

def triangle(values, size):
    import numpy as np
    if values is None or len(values) != size*(size+1)//2: return None
    result = np.zeros((size,size), dtype=float)
    result[np.tril_indices(size)] = values
    return result+result.T-np.diag(np.diag(result))

def indexed_table(text, header, symbols, ncols):
    lines = text.splitlines()
    starts = [i for i,x in enumerate(lines) if re.search(header,x,re.I)]
    for start in reversed(starts):
        rows = []
        for line in lines[start+1:start+len(symbols)+15]:
            tokens = line.split()
            if len(tokens)>=ncols+2 and tokens[0].isdigit():
                if int(tokens[0]) != len(rows)+1 or tokens[1] != symbols[len(rows)]: break
                try: rows.append([f(x) for x in tokens[2:2+ncols]])
                except ValueError: break
                if len(rows) == len(symbols): return rows
            elif rows: break
    return None

def polar_tensors(text):
    """Return every frequency block, including duplicates, never the last block."""
    blocks = []
    for hit in re.finditer(r"ALPHA AT\s+("+FLOAT+r")\s+EV\.", text):
        rest = text[hit.end():]
        rows = re.findall(r"\*=[XYZ]:\s*("+FLOAT+r")\s+("+FLOAT+r")\s+("+FLOAT+r")", rest[:1300])
        average = re.search(r"ISOTROPIC AVERAGE ALPHA\s*=\s*("+FLOAT+r")\s*A\.U\.\s*=\s*("+FLOAT+r")",rest[:1300])
        if len(rows)>=3 and average:
            tensor=[[f(x) for x in row] for row in rows[:3]]
            blocks.append({"frequency_eV": f(hit.group(1)), "tensor_bohr3": tensor,
                           "max_antisymmetric_component_bohr3":max(abs(tensor[i][j]-tensor[j][i]) for i in range(3) for j in range(3)),
                           "average_bohr3": f(average.group(1)), "average_A3": f(average.group(2))})
    return blocks

def sigma_pi_entries(text):
    """Parse paginated lower triangles, retaining orbital-group/atom indices."""
    start = text.find("SIGMA-PI BOND-ORDER MATRIX")
    if start < 0: return []
    section = text[start:].split("TOTAL ENERGY PARTITIONING")[0]
    labels = r"[SPDF]-(?:SIGMA|PI|DELL|DELTA|DEL)"
    header = re.compile(r"^\s*(?:"+labels+r"\s*)+$")
    row = re.compile(r"^\s*("+labels+r")\s+([A-Z][a-z]?)\s+(\d+)\s+(.*)$")
    keys, entries, offset, previous_columns = [], [], 0, 0
    for line in section.splitlines():
        if header.fullmatch(line):
            offset += previous_columns
            previous_columns = len(re.findall(labels,line)); continue
        hit = row.match(line)
        if not hit: continue
        key = (int(hit.group(3))-1,hit.group(1))
        if key not in keys: keys.append(key)
        try: values = [f(x) for x in hit.group(4).split()]
        except ValueError: continue
        for column,value in enumerate(values,offset):
            if column < len(keys):
                entries.append({"atom_i":key[0],"basis_i":key[1],"atom_j":keys[column][0],
                                "basis_j":keys[column][1],"value":value})
    return entries

def parse_mopac(directory, symbols, pair_indices=None, reconstruct_mulliken=False):
    import numpy as np
    directory = Path(directory); text = (directory/"input.out").read_text(errors="replace")
    aux, errors = read_aux(directory/"input.aux")
    n = len(symbols)
    net = indexed_table(text,r"NET ATOMIC CHARGES",symbols,1)
    mullik = indexed_table(text,r"MULLIKEN POPULATIONS AND CHARGES",symbols,2)
    esp = indexed_table(text,r"^\s*ELECTROSTATIC POTENTIAL CHARGES\s*$",symbols,1)
    bond_matrix = triangle(aux.get("BOND_ORDERS"),n)
    pairs = pair_indices if pair_indices is not None else [(i,j) for i in range(n) for j in range(i)]
    pair_set = set((max(i,j),min(i,j)) for i,j in pairs)
    polar = polar_tensors(text)
    fatal = re.findall(r".*(?:does not work|NOT AVAILABLE WITH UHF|SCF DOES NOT CONVERGE|SCF FAILED|Errors detected in keywords|polarizability failed).*",text,re.I)
    result = {
        "normal_end": "JOB ENDED NORMALLY" in text, "property_failure_lines": list(dict.fromkeys(x.strip() for x in fatal)),
        "parse_errors": errors,
        "heat_of_formation_kcal_mol": scalar(text,r"FINAL HEAT OF FORMATION\s*=\s*("+FLOAT+r")\s*KCAL"),
        "gradient_norm_kcal_mol_A": scalar(text,r"GRADIENT NORM\s*=\s*("+FLOAT+r")"),
        "total_energy_eV": scalar(text,r"TOTAL ENERGY\s*=\s*("+FLOAT+r")\s*EV"),
        "electronic_energy_eV": scalar(text,r"ELECTRONIC ENERGY\s*=\s*("+FLOAT+r")\s*EV"),
        "core_core_repulsion_eV": scalar(text,r"CORE-CORE REPULSION\s*=\s*("+FLOAT+r")\s*EV"),
        "dispersion_energy_kcal_mol": scalar(text,r"DISPERSION ENERGY\s*=\s*("+FLOAT+r")"),
        "hydrogen_bond_energy_kcal_mol": scalar(text,r"HYDROGEN BOND(?:ING)? ENERGY\s*=\s*("+FLOAT+r")"),
        "dielectric_energy_eV": scalar(text,r"DIELECTRIC ENERGY\s*=\s*("+FLOAT+r")"),
        "cosmo_area_A2": scalar(text,r"COSMO AREA\s*=\s*("+FLOAT+r")"),
        "cosmo_volume_A3": scalar(text,r"COSMO VOLUME\s*=\s*("+FLOAT+r")"),
        "spin_Sz": scalar(text,r"\(SZ\)\s*=\s*("+FLOAT+r")"),
        "spin_S2": scalar(text,r"\(S\*\*2\)\s*=\s*("+FLOAT+r")"),
        "dipole_Debye": aux.get("DIP_VEC:DEBYE"),
        "net_charges_e": [x[0] for x in net] if net else None,
        "mulliken_charges_e": [x[1] for x in mullik] if mullik else aux.get("MULLIKEN_ATOM_CHARGES"),
        "esp_charges_e": [x[0] for x in esp] if esp else None,
        "ao_atom_index_1based": aux.get("AO_ATOMINDEX"), "ao_types":aux.get("ATOM_SYMTYPE"),
        "ao_population_e": aux.get("AO_CHARGES"), "gradient_kcal_mol_A": aux.get("GRADIENTS:KCAL/MOL/ANGSTROM"),
        "valences": np.diag(bond_matrix).tolist() if bond_matrix is not None else None,
        "bond_orders": [{"i":i,"j":j,"value":float(bond_matrix[i,j])} for i,j in pairs] if bond_matrix is not None else None,
        "sigma_pi_entries":sigma_pi_entries(text),
        "polar_blocks":polar,
        "static_polar_block":next((x for x in polar if x["frequency_eV"]==0),None),
        "enpart_one_center_eV":[], "enpart_pairs_eV":[], "super_heavy_atom_rows":[],
        "mulliken_overlap_population_pairs": None,
        "STATIC_finite_field_tensors_bohr3":{},
    }
    for name in ("Heat of Formation","Dipole Moment"):
        marker="Polarizability Tensor from "+name+":"
        if marker in text:
            part=text.split(marker,1)[1].split("ROOT NO.",1)[0]
            lower=[]
            for line in part.splitlines():
                t=line.split()
                if t and t[0] in ("1","2","3") and len(t)==int(t[0])+1:
                    try: lower.extend(f(x) for x in t[1:])
                    except ValueError: pass
            tensor=triangle(lower,3)
            if tensor is not None: result["STATIC_finite_field_tensors_bohr3"][name]=tensor.tolist()
    eig, occ = aux.get("EIGENVALUES"), aux.get("MOLECULAR_ORBITAL_OCCUPANCIES")
    if isinstance(eig,list) and isinstance(occ,list) and len(eig)==len(occ):
        filled = [i for i,x in enumerate(occ) if x>1e-6]
        result["homo_eV"] = eig[max(filled)] if filled else None
        result["lumo_eV"] = eig[max(filled)+1] if filled and max(filled)+1<len(eig) else None
    else: result.update(homo_eV=None,lumo_eV=None)
    super_homo=scalar(text,r"Ehomo:\s*("+FLOAT+r")")
    super_lumo=scalar(text,r"Elumo:\s*("+FLOAT+r")")
    if super_homo is not None: result["homo_eV"]=super_homo
    if super_lumo is not None: result["lumo_eV"]=super_lumo
    for line in text.splitlines():
        tokens = line.split()
        try:
            if len(tokens)==5 and tokens[0] in symbols and tokens[1].isdigit():
                # One-center and SUPER have identical shapes; isolate by section below.
                pass
            if len(tokens)==11 and tokens[0] in symbols and tokens[1].isdigit() and tokens[2] in symbols and tokens[3].isdigit():
                i,j=int(tokens[1])-1,int(tokens[3])-1
                if (max(i,j),min(i,j)) in pair_set:
                    result["enpart_pairs_eV"].append({"i":i,"j":j,"J_K_EE_EN_NN_C_total":[f(x) for x in tokens[4:]]})
        except ValueError: continue
    for name,begin,end in (("enpart_one_center_eV","ATOM      E-E","TWO-CENTER TERMS"),("super_heavy_atom_rows","Dn(r)","Total:")):
        if begin not in text: continue
        section=text.split(begin,1)[1].split(end,1)[0]
        for line in section.splitlines():
            t=line.split()
            if len(t)==5 and t[0] in symbols and t[1].isdigit():
                try: result[name].append({"atom_index":int(t[1])-1,"values":[f(x) for x in t[2:]]})
                except ValueError: pass
    if reconstruct_mulliken and isinstance(occ,list):
        nao=len(occ); overlap=triangle(aux.get("OVERLAP_MATRIX"),nao); coeff=aux.get("EIGENVECTORS"); mapping=aux.get("AO_ATOMINDEX")
        if overlap is not None and coeff is not None and len(coeff)==nao*nao and mapping is not None:
            eigS,u=np.linalg.eigh(overlap)
            if eigS.min()>1e-8:
                c=(u/np.sqrt(eigS))@u.T@np.array(coeff).reshape(nao,nao).T
                q=((c*np.array(occ))@c.T)*overlap
                atomq=np.array([q[np.array(mapping)==i+1,:].sum() for i in range(n)])
                core=np.array(aux["ATOM_CORE"]); observed=result["mulliken_charges_e"]
                result["mulliken_reconstruction_charge_max_error_e"]=float(np.max(np.abs(core-atomq-np.array(observed)))) if observed else None
                result["mulliken_overlap_population_pairs"]=[{"i":i,"j":j,"population_e":float(2*q[np.ix_(np.array(mapping)==i+1,np.array(mapping)==j+1)].sum())} for i,j in pairs]
            else: result["parse_errors"].append("OVERLAP_NOT_POSITIVE_DEFINITE")
    return result

def parse_xtb(directory, symbols):
    directory=Path(directory); text=(directory/"process.out").read_text(errors="replace"); n=len(symbols)
    raw=json.loads((directory/"xtbout.json").read_text()) if (directory/"xtbout.json").exists() else {}
    result={
        "normal_end":"normal termination of xtb" in text.lower(), "method":raw.get("method"), "version":raw.get("xtb version"),
        "energy_Eh":scalar(text,r"\bTOTAL ENERGY\s+("+FLOAT+r")\s*Eh"),
        "dipole_Debye":[float(x)*AU_DIPOLE_TO_DEBYE for x in raw["dipole / a.u."]] if "dipole / a.u." in raw else None,
        "charges_e":raw.get("partial charges"), "D4_atomic_C6_au":[], "D4_atomic_alpha_bohr3":[],
        "molecular_quadrupole_traceless_au":None, "wiberg_pairs":[], "fukui":None,
        "IP_eV":scalar(text,r"delta SCC IP \(eV\):\s*("+FLOAT+r")"),
        "EA_eV":scalar(text,r"delta SCC EA \(eV\):\s*("+FLOAT+r")"),
        "Gsolv_Eh":scalar(text,r"->\s*Gsolv\s+("+FLOAT+r")"),
        "NFOD_e":scalar(text,r"NFOD\s*:\s*("+FLOAT+r")"),
        "FOD_atom_e":[f(x) for x in (directory/"fod").read_text().split()] if (directory/"fod").exists() else None,
        "frequencies_cm_inverse":raw.get("vibrational frequencies / rcm"),
        "IR_km_mol":raw.get("IR intensities / km/mol"),
        "ZPE_Eh":scalar(text,r"zero point energy\s+("+FLOAT+r")"),
        "enthalpy_Eh":scalar(text,r"TOTAL ENTHALPY\s+("+FLOAT+r")"),
        "thermo_tot_H_cal_mol_Cp_cal_mol_K_S_cal_mol_K_S_J_mol_K":None,
        "warnings":[x.strip() for x in text.splitlines() if "Hessian on incompletely optimized" in x],
    }
    orbitals=raw.get("orbital energies / eV",[]); occ=raw.get("fractional occupation",[])
    occupied=[i for i,x in enumerate(occ) if x>1e-6]
    h=max(occupied) if occupied else None
    result.update(homo_eV=orbitals[h] if h is not None else None,lumo_eV=orbitals[h+1] if h is not None and h+1<len(orbitals) else None)
    for line in text.splitlines():
        t=line.split()
        if len(t)==8 and t[0].isdigit() and t[1].isdigit() and t[2] in symbols:
            try: result["D4_atomic_C6_au"].append(f(t[6])); result["D4_atomic_alpha_bohr3"].append(f(t[7]))
            except ValueError: pass
        if len(t)==5 and t[0]=="TOT":
            try: result["thermo_tot_H_cal_mol_Cp_cal_mol_K_S_cal_mol_K_S_J_mol_K"]=[f(x) for x in t[1:]]
            except ValueError: pass
    # Actual xTB atomic table has seven columns, not the eight used by older variants.
    if not result["D4_atomic_C6_au"]:
        for line in text.splitlines():
            t=line.split()
            if len(t)==7 and t[0].isdigit() and t[1].isdigit() and t[2] in symbols:
                try: result["D4_atomic_C6_au"].append(f(t[5])); result["D4_atomic_alpha_bohr3"].append(f(t[6]))
                except ValueError: pass
    if "molecular quadrupole (traceless):" in text:
        part=text.split("molecular quadrupole (traceless):")[-1]
        hit=re.search(r"full:\s*("+FLOAT+r")\s+("+FLOAT+r")\s+("+FLOAT+r")\s+("+FLOAT+r")\s+("+FLOAT+r")\s+("+FLOAT+r")",part)
        if hit: result["molecular_quadrupole_traceless_au"]=[f(x) for x in hit.groups()]
    if "Fukui functions:" in text:
        rows=re.findall(r"(?m)^\s*(\d+)\s*([A-Z][a-z]?)\s+("+FLOAT+r")\s+("+FLOAT+r")\s+("+FLOAT+r")\s*$",text.split("Fukui functions:")[-1])
        if len(rows)>=n and [int(x[0]) for x in rows[:n]]==list(range(1,n+1)):
            result["fukui"]=[[f(x) for x in row[2:]] for row in rows[:n]]
    if (directory/"wbo").exists():
        for line in (directory/"wbo").read_text().splitlines():
            t=line.split()
            if len(t)==3: result["wiberg_pairs"].append({"i":int(t[0])-1,"j":int(t[1])-1,"value":f(t[2])})
    if (directory/"gradient").exists():
        rows=[x.split() for x in (directory/"gradient").read_text().splitlines()]
        coords=[t for t in rows if len(t)==4 and t[3] in symbols]
        gradients=[[f(x) for x in t] for t in rows if len(t)==3 and all(re.fullmatch(FLOAT,x) for x in t)]
        if len(coords)==n and len(gradients)==n and [t[3] for t in coords]==symbols:
            result["gradient_Eh_bohr"]=gradients
            result["forces_eV_A"]=[[-x*EH_TO_EV/BOHR_TO_A for x in row] for row in gradients]
    return result

def review_molecule(path):
    mol=Path(path); rows=[]
    geometry=json.loads((mol/"synthetic_geometry.json").read_text()); symbols=geometry["atoms"]; n=len(symbols)
    for task in sorted(x for x in mol.iterdir() if x.is_dir()):
        old=json.loads((task/"result.json").read_text())
        values=parse_mopac(task,symbols,reconstruct_mulliken=task.name=="pm7_B_large") if old["family"]=="mopac" else parse_xtb(task,symbols)
        required=[]
        if old["family"]=="mopac":
            required=["heat_of_formation_kcal_mol"]
            if task.name.startswith("pm7_B"):
                required+=["gradient_norm_kcal_mol_A","total_energy_eV","electronic_energy_eV","core_core_repulsion_eV",
                           "mulliken_charges_e","ao_population_e","gradient_kcal_mol_A","bond_orders","sigma_pi_entries","enpart_pairs_eV"]
            if "POLAR" in task.name and "negative" not in task.name: required+=["static_polar_block"]
            if "STATIC" in task.name: required+=["STATIC_finite_field_tensors_bohr3"]
            if "ESP" in task.name: required+=["esp_charges_e"]
            if task.name.startswith("pm7_C"): required+=["dielectric_energy_eV","cosmo_area_A2","cosmo_volume_A3"]
        else:
            required=["energy_Eh"]
            if task.name=="xtb_singlepoint": required+=["dipole_Debye","charges_e","D4_atomic_C6_au","D4_atomic_alpha_bohr3","molecular_quadrupole_traceless_au","wiberg_pairs","homo_eV","lumo_eV"]
            if "vipea" in task.name: required+=["IP_eV","EA_eV"]
            if "vfukui" in task.name: required+=["fukui"]
            if "ALPB" in task.name: required+=["Gsolv_Eh"]
            if "fod" in task.name: required+=["NFOD_e","FOD_atom_e"]
            if "gradient" in task.name: required+=["forces_eV_A"]
            if "hessian" in task.name: required+=["frequencies_cm_inverse","IR_km_mol","ZPE_Eh","enthalpy_Eh","thermo_tot_H_cal_mol_Cp_cal_mol_K_S_cal_mol_K_S_J_mol_K"]
        missing=[k for k in required if values.get(k) is None or values.get(k)==[] or values.get(k)=={}]
        length_issues=[]
        for key,expected in (("net_charges_e",n),("mulliken_charges_e",n),("esp_charges_e",n),("gradient_kcal_mol_A",3*n),
                             ("charges_e",n),("D4_atomic_C6_au",n),("D4_atomic_alpha_bohr3",n),("FOD_atom_e",n),("fukui",n),
                             ("forces_eV_A",n),("frequencies_cm_inverse",3*n),("IR_km_mol",3*n)):
            if values.get(key) is not None and values.get(key)!=[] and len(values[key])!=expected: length_issues.append(key)
        outcome="NUMERICAL_PROPERTIES_PRESENT"
        if old["status"]!="PROCESS_SUCCESS" or values.get("property_failure_lines"): outcome="CALCULATION_OR_PROPERTY_FAILED"
        elif missing or length_issues or values.get("parse_errors"): outcome="NUMERICAL_PARSE_INCOMPLETE"
        rows.append({"source":str(mol.parent),"molecule":mol.name,"task":task.name,"review_status":outcome,
                     "missing_numeric_properties":missing,"length_issues":length_issues,"values":values,"worker_pid":os.getpid()})
    return rows

def review_capability(roots, workers):
    rows=[]; conclusions=collections.defaultdict(collections.Counter)
    molecules=[str(mol) for root in roots for mol in sorted(Path(root).iterdir()) if mol.is_dir()]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for group in pool.map(review_molecule,molecules,chunksize=1): rows.extend(group)
    for row in rows: conclusions[row["task"]][row["review_status"]]+=1
    return {"scope":"NUMERICAL_REVIEW_SYNTHETIC_ONLY","sources":[str(x) for x in roots],
            "workers":workers,"worker_pids":sorted(set(x["worker_pid"] for x in rows)),
            "outcomes":{k:dict(v) for k,v in conclusions.items()},"rows":rows}

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--review-capability",required=True,action="append"); p.add_argument("--output",required=True)
    p.add_argument("--workers",type=int,default=16); a=p.parse_args()
    if not os.environ.get("SLURM_JOB_ID") or int(os.environ.get("SLURM_CPUS_PER_TASK","0"))<16 or not 16<=a.workers<=int(os.environ["SLURM_CPUS_PER_TASK"]):
        raise SystemExit("Numerical review requires Slurm allocation >=16 CPUs and effective workers <= allocation")
    for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","BLIS_NUM_THREADS"): os.environ[name]="1"
    output=Path(a.output)
    report=review_capability(a.review_capability,a.workers)
    report.update(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), seed=20261010,
                  slurm_job_id=os.environ["SLURM_JOB_ID"], python_logical_entry=sys.executable,
                  python_version=sys.version, numpy_version=importlib.metadata.version("numpy"),
                  input_execution_metadata=[json.loads((Path(root)/"metadata.json").read_text()) for root in a.review_capability])
    with output.open("x",encoding="utf-8") as h:
        json.dump(report,h,indent=2,allow_nan=False); h.write("\n"); h.flush(); os.fsync(h.fileno())
    print(str(output))
