#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import argparse
import time
import re
import numpy as np
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# 引入 RDKit 库用于结构解析和 SMILES 处理
from rdkit import Chem
from rdkit.Chem import AllChem

##############################
# 几何优化过程帧处理模块
##############################
def extract_atom_symbols(file_path):
    """
    从 aux 文件中提取原子符号列表。
    例如，文件中会有如下段落：
      ATOM_EL[062]=
       O  C  N  C  C  C  ...  H
    返回一个列表，如 ["O", "C", "N", "C", ...]
    """
    symbols = []
    with open(file_path, 'r') as f:
        lines = f.readlines()
    for idx, line in enumerate(lines):
        if "ATOM_EL" in line:
            j = idx + 1
            while j < len(lines):
                if "ATOM_CORE" in lines[j]:
                    break
                symbols.extend(lines[j].strip().split())
                j += 1
            break
    # print('symbols:', symbols)
    return symbols

def parse_aux_file(file_path):
    """
    解析 MOPAC aux 文件，返回一个帧列表，每一帧为字典，包含：
      'energy': 生成热（浮点数，单位：kcal/mol）
      'coords': 坐标列表，每一行为一个原子坐标（浮点数列表）
    同时通过解析 "ATOM_EL" 行确定原子数。
    """
    frames = []
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # 从 "ATOM_EL" 行中解析原子数（例如 "ATOM_EL[062]=" 表示 62 个原子）
    num_atoms = None
    for line in lines:
        if "ATOM_EL" in line:
            match = re.search(r'\[(\d+)\]', line)
            if match:
                num_atoms = int(match.group(1))
                break
    if num_atoms is None:
        raise ValueError(f"无法在文件 {file_path} 中解析原子数。")
    
    i = 0
    while i < len(lines):
        if "HEAT_OF_FORM_UPDATED" in lines[i]:
            energy_line = lines[i].strip()
            try:
                energy_str = energy_line.split('=')[1].strip()
                energy = float(energy_str.replace('D','e'))
            except Exception as e:
                raise ValueError(f"解析能量时出错：{energy_line}") from e

            j = i
            coords = []
            while j < len(lines):
                if "ATOM_X_UPDATED:ANGSTROMS" in lines[j]:
                    start = j + 1
                    for k in range(start, start + num_atoms):
                        try:
                            coord_values = list(map(float, lines[k].split()))
                            coords.append(coord_values)
                        except Exception as e:
                            raise ValueError(f"解析坐标时出错，行：{lines[k]}") from e
                    break
                j += 1
            if coords:
                frames.append({'energy': energy, 'coords': coords})
            i = j + num_atoms
        else:
            i += 1
    return frames

def select_frames(frames, RT):
    """
    根据能量变化选择帧：
      - 初始帧始终记录，同时初始的能量极大值和极小值均为第一帧能量。
      - 当能量下降时，如果比之前的能量极大值下降超过 RT，则记录该帧，并更新能量极大值。
      - 当能量上升时，如果比之前的能量极小值上升超过 RT，则记录该帧，并更新能量极小值。
    返回选中帧的列表，每一项为 (原始帧索引, 帧数据字典)。
    """
    if not frames:
        return []
    selected_frames = []
    selected_frames.append((0, frames[0]))
    last_energy_max = frames[0]['energy']
    last_energy_min = frames[0]['energy']
    
    for i in range(1, len(frames)):
        current_energy = frames[i]['energy']
        if current_energy < last_energy_max - RT:
            selected_frames.append((i, frames[i]))
            last_energy_max = current_energy
        elif current_energy > last_energy_min + RT:
            selected_frames.append((i, frames[i]))
            last_energy_min = current_energy
    return selected_frames

def write_xyz_with_symbols(frame, atom_symbols, output_filename):
    """
    将单个帧写出为 xyz 格式文件。
    格式：
      第一行：原子数
      第二行：SCF Energy: ... kcal/mol (PM7 optimized)
      后续每行：原子符号及对应的 x, y, z 坐标（格式化输出）
    """
    num_atoms = len(frame['coords'])
    energy = frame['energy']
    with open(output_filename, 'w') as f:
        f.write(f"{num_atoms}\n")
        f.write(f"SCF Energy: {energy:.6f} kcal/mol (PM7 optimized)\n")
        for sym, coord in zip(atom_symbols, frame['coords']):
            coord_str = " ".join(f"{x:12.6f}" for x in coord)
            f.write(f"{sym} {coord_str}\n")

def process_aux_file(aux_file_path, output_dir, RT):
    """
    处理单个 aux 文件：
      - 解析出帧数据（能量和坐标）
      - 根据能量变化条件筛选帧
      - 将选中的每一帧写为 xyz 文件，命名格式为 {base_name}_{帧编号}.xyz
    """
    frames = parse_aux_file(aux_file_path)
    selected = select_frames(frames, RT)
    atom_symbols = extract_atom_symbols(aux_file_path)
    base_name = os.path.splitext(os.path.basename(aux_file_path))[0]
    for count, (idx, frame) in enumerate(selected, start=1):
        output_filename = os.path.join(output_dir, f"{base_name}_{count}.xyz")
        write_xyz_with_symbols(frame, atom_symbols, output_filename)

##############################
# 文件读取与写入函数（原主脚本部分）
##############################
def read_xyz_with_smiles(file_path):
    """
    读取标准 XYZ 文件（第一行原子数，第二行名称，接下来为坐标，最后一行为 SMILES）。
    返回：num_atoms, atoms, coords, smiles
    """
    with open(file_path, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    try:
        num_atoms = int(lines[0])
    except Exception as e:
        raise ValueError(f"无法解析原子数：{lines[0]}，错误：{e}")
    # if len(lines) < num_atoms + 3:
    #     raise ValueError("文件行数不足，可能缺少 SMILES 行")
    charge_line = lines[1]
    try:
        charge = int(float(charge_line))
        coord_start = 2
    except ValueError:          # 旧格式：第二行是标题
        charge = 0
        coord_start = 2           # 保持向后兼容
    smiles_test = lines[-1].split()
    if len(smiles_test) == 4:
        coord_lines = lines[coord_start:]
        smiles = None
    else:
        coord_lines = lines[coord_start:-1]
        smiles = lines[-1]
    if len(coord_lines) != num_atoms:
        raise ValueError(f"坐标行数({len(coord_lines)})与原子数({num_atoms})不匹配")
    atoms = []
    coords = []
    for line in coord_lines:
        parts = line.split()
        atom = parts[0]
        x, y, z = map(float, parts[1:4])
        atoms.append(atom)
        coords.append([x, y, z])
    return num_atoms, atoms, np.array(coords), smiles, charge

def write_xyz(file_path, num_atoms, atoms, coords, smiles=None):
    """
    将原子信息写入 XYZ 文件。如果提供 smiles，则写在最后一行。
    """
    with open(file_path, 'w') as f:
        f.write(f"{num_atoms}\n")
        f.write("Generated by compute_charge_parallel.py\n")
        for atom, (x, y, z) in zip(atoms, coords):
            f.write(f"{atom}\t{x:.6f}\t{y:.6f}\t{z:.6f}\n")
        if smiles is not None:
            f.write(smiles + "\n")

##############################
# SMILES解析及分组函数（原主脚本部分）
##############################
def get_fragment_atom_counts(smiles):
    """
    根据 SMILES 字符串返回各个碎片中原子的数量信息。
    返回列表，每个元素对应一个碎片，格式为 (非H原子数, H原子数)。
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("SMILES解析失败")
    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=False)
    counts = []
    for frag in frags:
        frag_with_H = Chem.AddHs(frag)
        n_heavy = sum(1 for atom in frag_with_H.GetAtoms() if atom.GetSymbol() != "H")
        n_H = sum(1 for atom in frag_with_H.GetAtoms() if atom.GetSymbol() == "H")
        counts.append((n_heavy, n_H))
    return counts

def separate_secondary_by_smiles(smiles, atoms, coords, min_tol=0.8, max_tol=1.2, shift_step=0.5, max_iter=50):
    """
    利用 SMILES 信息对次分子进行智能分离。
    返回调整后的坐标和是否进行了调整的标志。
    """
    try:
        counts = get_fragment_atom_counts(smiles)
    except Exception as e:
        logging.warning(f"SMILES解析失败: {e}，跳过次分子分离")
        return coords, False

    if len(counts) < 2:
        return coords, False

    primary_heavy = counts[0][0]
    primary_H = counts[0][1]
    secondary_counts = counts[1:]
    sec_heavy_total = sum(x[0] for x in secondary_counts)
    sec_H_total = sum(x[1] for x in secondary_counts)

    total_expected = primary_heavy + sec_heavy_total + primary_H + sec_H_total
    # if total_expected != len(atoms):
    #     logging.warning(f"原子数不匹配：预期 {total_expected}，实际 {len(atoms)}。可能原子排序与预设不一致。")

    idx_primary_heavy = list(range(0, primary_heavy))
    idx_secondary_heavy = []
    start = primary_heavy
    secondary_heavy_indices = []
    for cnt in secondary_counts:
        n = cnt[0]
        inds = list(range(start, start + n))
        secondary_heavy_indices.append(inds)
        start += n
    idx_primary_H = list(range(primary_heavy + sec_heavy_total, primary_heavy + sec_heavy_total + primary_H))
    secondary_H_indices = []
    start = primary_heavy + sec_heavy_total + primary_H
    for cnt in secondary_counts:
        n = cnt[1]
        inds = list(range(start, start + n))
        secondary_H_indices.append(inds)
        start += n

    group_primary = idx_primary_heavy + idx_primary_H
    secondary_groups = []
    for i in range(len(secondary_counts)):
        group = secondary_heavy_indices[i] + secondary_H_indices[i]
        secondary_groups.append(group)

    groups = {"primary": group_primary}
    for i in range(len(secondary_groups)):
        groups[f"secondary_{i}"] = secondary_groups[i]

    new_coords = coords.copy()

    def radius(atom_symbol):
        # 共价半径（单位 Å）
        COV_RADII = {
            'H': 0.32, 'C': 0.77, 'N': 0.70, 'O': 0.66, 'F': 0.64,
            'P': 1.10, 'S': 1.04, 'Cl': 0.99, 'Br': 1.14, 'I': 1.33,
            'Na': 1.54, 'K': 2.03, 'Mg': 1.36, 'Ca': 1.74, 'Li': 1.23,
            'Al': 1.18, 'Si': 1.17, 'Be': 0.89, 'B': 0.82, 'Ge': 1.22, 'Ga': 1.26, 'As': 1.21,
            'Sn': 1.40, 'Sb': 1.41, 'Pb': 1.47, 'Bi': 1.46,
            'Sc': 1.44, 'Ti': 1.32, 'V': 1.22, 'Cr': 1.18, 'Mn': 1.17,
            'Fe': 1.17, 'Co': 1.16, 'Ni': 1.15, 'Cu': 1.17, 'Zn': 1.25,
            'Ru': 1.25, 'Rh': 1.25, 'Pd': 1.28, 'Os': 1.26, 'Ir': 1.27, 'Pt': 1.30,
            'Ag': 1.34, 'Au': 1.34, 'Cd': 1.48, 'Hg': 1.44,
        }
        return COV_RADII.get(atom_symbol, 0.7)

    def groups_overlap(idxs1, idxs2):
        for i in idxs1:
            for j in idxs2:
                r1 = radius(atoms[i])
                r2 = radius(atoms[j])
                thresh = (r1 + r2) * max_tol
                if np.linalg.norm(new_coords[i] - new_coords[j]) < thresh:
                    return True
        return False

    directions = {}
    for key in groups:
        if key.startswith("secondary"):
            vec = np.random.randn(3)
            vec /= np.linalg.norm(vec)
            directions[key] = vec

    for it in range(max_iter):
        moved = False
        for key in [k for k in groups if k.startswith("secondary")]:
            if groups_overlap(groups["primary"], groups[key]):
                new_coords[groups[key]] += shift_step * directions[key]
                moved = True
        sec_keys = [k for k in groups if k.startswith("secondary")]
        for i in range(len(sec_keys)):
            for j in range(i+1, len(sec_keys)):
                k1 = sec_keys[i]
                k2 = sec_keys[j]
                if groups_overlap(groups[k1], groups[k2]):
                    center1 = np.mean(new_coords[groups[k1]], axis=0)
                    center2 = np.mean(new_coords[groups[k2]], axis=0)
                    if np.linalg.norm(center1) < np.linalg.norm(center2):
                        new_coords[groups[k1]] += shift_step * directions[k1]
                    else:
                        new_coords[groups[k2]] += shift_step * directions[k2]
                    moved = True
        if not moved:
            logging.info(f"次分子分离完成，迭代次数 {it}")
            return new_coords, True
    logging.warning("达到最大迭代次数，次分子可能仍存在部分重叠。")
    return new_coords, True

##############################
# MOPAC 相关函数
##############################
def create_mopac_input(file_path, atoms, coords, charge,
                       output_directory, keyword="PM7", remark="single point"):
    base = os.path.splitext(os.path.basename(file_path))[0]
    input_file = os.path.join(output_directory, base + '.mop')
    # 若用户已自带 CHARGE，避免重复
    if f"CHARGE=" not in keyword.upper():
        keyword += f" CHARGE={charge}"
    header = f"{keyword}\n\n{base} - {remark}\n"
    lines = header
    for atom, (x, y, z) in zip(atoms, coords):
        lines += f"{atom:2s}\t{x:12.6f}\t{y:12.6f}\t{z:12.6f}\n"
    with open(input_file, 'w') as f:
        f.write(lines)
    return input_file

def run_mopac(input_file, cores):
    """
    运行 MOPAC 并返回返回码。
    若任务运行超过一小时（3600秒）仍未结束，则中断任务并返回错误码。
    """
    try:
        env = os.environ.copy()
        env['OMP_NUM_THREADS'] = str(cores)
        mopac_log = input_file + ".run.log"
        with open(mopac_log, 'w') as lf:
            # 设置 timeout 参数为3600秒（1小时）
            result = subprocess.run(["mopac", input_file],
                                    stdout=lf, stderr=lf, text=True,
                                    env=env, timeout=3600)
        if result.returncode != 0:
            logging.error(f"MOPAC执行失败: {input_file}，详情请查看 {mopac_log}")
        return result.returncode
    except subprocess.TimeoutExpired:
        logging.error(f"MOPAC执行超时：任务 {input_file} 超过1小时未结束，已中断。")
        return -1
    except Exception as e:
        logging.exception(f"MOPAC执行异常: {input_file}, 错误: {e}")
        return -1

def check_output(output_file):
    """
    检查 MOPAC 输出文件是否包含所需信息。
    """
    if not os.path.exists(output_file):
        return False
    with open(output_file, 'r') as f:
        content = f.read()
    return ("FINAL HEAT OF FORMATION" in content and 
            "NET ATOMIC CHARGES AND DIPOLE CONTRIBUTIONS" in content)

def extract_results(output_file, atoms, coords, output_directory):
    """
    提取能量、电荷及优化后几何坐标，并写入 .xyz 文件。
    """
    with open(output_file, 'r') as f:
        lines = f.readlines()
    
    scf_energy = None
    charges = []
    new_coords = None

    for i, line in enumerate(lines):
        if "FINAL HEAT OF FORMATION" in line:
            match = re.search(r'(-?\d+\.\d+)', line)
            if match:
                scf_energy = float(match.group(1))
        if "NET ATOMIC CHARGES AND DIPOLE CONTRIBUTIONS" in line:
            start_index = i + 3
            for charge_line in lines[start_index:]:
                if not charge_line.strip() or "DIPOLE" in charge_line:
                    break
                parts = charge_line.split()
                try:
                    charges.append(float(parts[2]))
                except (IndexError, ValueError):
                    break

    cart_indices = [i for i, line in enumerate(lines) if "CARTESIAN COORDINATES" in line]
    if cart_indices:
        chosen_index = cart_indices[-1]
        coord_lines = []
        for j in range(chosen_index + 1, len(lines)):
            parts = lines[j].split()
            if len(parts) >= 5:
                try:
                    float(parts[2])
                    float(parts[3])
                    float(parts[4])
                    coord_lines.append(lines[j])
                except ValueError:
                    continue
            if len(coord_lines) >= len(atoms):
                break
        if len(coord_lines) >= len(atoms):
            new_coords = []
            for cline in coord_lines[:len(atoms)]:
                parts = cline.split()
                try:
                    x = float(parts[2])
                    y = float(parts[3])
                    z = float(parts[4])
                    new_coords.append([x, y, z])
                except Exception as e:
                    logging.warning(f"解析坐标行失败: {cline}, 错误: {e}")
                    new_coords = None
                    break
    else:
        logging.warning("未找到 'CARTESIAN COORDINATES' 部分，使用原始坐标。")
    
    if new_coords and len(new_coords) == len(atoms):
        coords_to_write = new_coords
    else:
        coords_to_write = coords
        logging.warning("优化后坐标提取不完整，退回使用原始坐标。")
    
    if scf_energy is None or len(charges) != len(atoms):
        raise ValueError("输出文件信息不完整。")
    
    base = os.path.splitext(os.path.basename(output_file))[0]
    out_file = os.path.join(output_directory, re.sub(r'_new$', '', base) + ".xyz")
    with open(out_file, 'w') as outf:
        outf.write(f"{len(atoms)}\n")
        outf.write(f"SCF Energy: {scf_energy:.8f} kcal/mol (PM7 optimized)\n")
        for (atom, (x, y, z)), charge in zip(zip(atoms, coords_to_write), charges):
            outf.write(f"{atom:2s}\t{x:12.6f}\t{y:12.6f}\t{z:12.6f}\t{charge:12.6f}\n")
    return scf_energy, charges

def has_geometry_error(output_file):
    """
    判断输出文件是否包含 "GEOMETRY IN ERROR"。
    """
    if not os.path.exists(output_file):
        return False
    with open(output_file, 'r') as f:
        return any("GEOMETRY IN ERROR" in line for line in f)

def move_out_file(output_file, target_dir):
    """
    将指定文件移动到 target_dir 目录中。
    """
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
    base = os.path.basename(output_file)
    new_path = os.path.join(target_dir, base)
    try:
        os.rename(output_file, new_path)
    except Exception as e:
        logging.warning(f"移动文件 {output_file} 到 {target_dir} 失败：{e}")

def remove_mopac_temp_files(base, directory, remove_xyz=False, archive_dir=None):
    """
    移除 MOPAC 中间文件；当 archive_dir 不为 None 时，将 .out 文件移入该目录，其余删除。
    """
    suffixes = [".aux", ".arc", ".den", ".mop", ".mop.run.log"]
    if remove_xyz:
        suffixes.append(".xyz")
    out_file = os.path.join(directory, base + ".out")
    if archive_dir is not None:
        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir, exist_ok=True)
        if os.path.exists(out_file):
            try:
                new_path = os.path.join(archive_dir, base + ".out")
                os.rename(out_file, new_path)
            except Exception as e:
                logging.warning(f"移动文件 {out_file} 失败：{e}")
    else:
        suffixes.append(".out")
    for suf in suffixes:
        path = os.path.join(directory, base + suf)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logging.warning(f"删除文件 {path} 失败：{e}")

##############################
# 作业处理函数（增加 mode 与 geom_frames 参数）
##############################
def process_job(file_path, output_directory, cores,
                mode, geom_frames, max_retries=3,
                failed_dir="failed_outputs"):
    """
    处理单个作业：
      · 不再对次分子执行平移调整。
      · 若 SMILES 含多碎片（可能存在初始构象问题），直接跳过。
    """
    # ----- modified ----- 不再生成 _new.xyz -----
    used_file = file_path
    base = os.path.splitext(os.path.basename(used_file))[0]

    output_xyz = os.path.join(output_directory, f"{base}.xyz")
    output_out = os.path.join(output_directory, f"{base}.out")
    archive_dir = os.path.join(os.path.abspath(os.path.join(output_directory, os.pardir)), "out_files")

    if os.path.exists(output_xyz):
        return

    attempt = 0
    while attempt < max_retries:
        try:
            num_atoms, atoms, coords, smiles, mol_charge = read_xyz_with_smiles(used_file)

            # ------------------------------------------------

            # 依据 mode 生成关键字
            if mode == "geom":
                keyword = "PM7 AUX" if geom_frames else "PM7"
                remark = "geometry optimization"
            elif mode == "single":
                keyword = "PM7 1SCF"
                remark = "single point calculation"
            else:
                raise ValueError("未知的 mode 参数")

            input_file = create_mopac_input(
                used_file, atoms, coords, mol_charge,
                output_directory, keyword=keyword, remark=remark)

            return_code = run_mopac(input_file, cores)
            if return_code != 0:
                attempt += 1
                raise RuntimeError(f"MOPAC运行失败，返回码: {return_code}")

            if has_geometry_error(output_out):
                logging.error(f"[Fail] 几何修正后仍有错误，跳过作业: {output_out}")
                move_out_file(output_out, failed_dir)
                remove_mopac_temp_files(base, output_directory,
                                        remove_xyz=True, archive_dir=archive_dir)
                return

            if check_output(output_out):
                extract_results(output_out, atoms, coords, output_directory)
                if mode == "geom" and geom_frames:
                    aux_file = os.path.join(output_directory, base + ".aux")
                    if os.path.exists(aux_file):
                        frames_output_dir = os.path.join(
                            os.path.dirname(os.path.abspath(output_directory)), "geom_frames")
                        os.makedirs(frames_output_dir, exist_ok=True)
                        process_aux_file(aux_file, frames_output_dir, RT_value)
                    else:
                        logging.warning(f"未找到 aux 文件: {base}.aux")
                remove_mopac_temp_files(base, output_directory,
                                        remove_xyz=False, archive_dir=archive_dir)
                return
            else:
                attempt += 1
                raise RuntimeError(f"输出文件不完整: {output_out}")

        except Exception as e:
            attempt += 1
            # logging.error(f"[Error] 处理作业失败: {file_path}, 错误: {e}")
            if attempt >= max_retries:
                logging.error(f"[Fail] 达到最大重试次数，跳过作业: {file_path}")
                if os.path.exists(output_out):
                    move_out_file(output_out, failed_dir)
                remove_mopac_temp_files(base, output_directory,
                                        remove_xyz=True, archive_dir=archive_dir)
                return

##############################
# 主函数（增加 mode 与 geom_frames 参数）
##############################
def main(xyz_directory, output_directory, start_idx, end_idx, max_jobs, cores, user, structure_nums, mode, geom_frames, save_wavefunctions=False):
    """
    主函数，批量提交并监控 MOPAC 作业。
    """
    # 若在 SLURM 环境下，自动调整并发任务数
    # if "SLURM_CPUS_ON_NODE" in os.environ:
    #     total_allocated_cores = int(os.environ["SLURM_CPUS_ON_NODE"])
    #     max_jobs_slurm = total_allocated_cores // cores
    #     if max_jobs_slurm < max_jobs:
    #         logging.info(f"检测到 SLURM 环境：预分配核数为 {total_allocated_cores}，调整 max_jobs 从 {max_jobs} 至 {max_jobs_slurm}")
    #         max_jobs = max_jobs_slurm

    if not os.path.exists(output_directory):
        os.makedirs(output_directory, exist_ok=True)

    # 以下内容保持原有逻辑……
    low, high = start_idx, end_idx
    # while low < high:
    #     mid = (low + high + 1) // 2
    #     file_path = os.path.join(xyz_directory, f"principal_{mid:08}_01.xyz")
    #     if os.path.exists(file_path):
    #         low = mid
    #     else:
    #         high = mid - 1
    # actual_max_idx = low
    # if end_idx > actual_max_idx:
    #     end_idx = actual_max_idx
    #     logging.info(f"指定的 end_idx 超出范围，已调整为实际最大序号 {end_idx}。")
    logging.info(f"处理分子序号范围：{start_idx} 至 {end_idx}。")
    
    job_files = []
    for idx in range(start_idx, end_idx + 1):
        for struct_idx in range(1, structure_nums + 1):
            job_files.append(os.path.join(xyz_directory, f"principal_{idx:08}_{struct_idx:02}.xyz"))
    total_jobs = len(job_files)
    logging.info(f"找到 {total_jobs} 个XYZ文件。")
    if total_jobs == 0:
        logging.info("没有需要处理的作业。")
        return
    
    processed_count = 0
    with ThreadPoolExecutor(max_workers=max_jobs) as executor:
        future_to_job = {executor.submit(process_job, file_path, output_directory, cores, mode, geom_frames, 3): file_path for file_path in job_files}
        for future in as_completed(future_to_job):
            file_path = future_to_job[future]
            try:
                future.result()
            except Exception as e:
                logging.exception(f"[Exception] 作业处理失败: {file_path}, 错误: {e}")
            processed_count += 1
            if processed_count % 10000 == 0:
                logging.info(f"已完成结构数: {processed_count}, 当前结构: {file_path}")
    logging.info("所有作业已处理完成。")


##############################
# 日志配置及脚本入口（增加 mode 与 geom_frames 参数）
##############################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MOPAC 并行任务提交脚本，支持模式选择和几何优化帧生成。")
    parser.add_argument("--xyz_dir", type=str, required=True, help="XYZ 文件所在目录")
    parser.add_argument("--output_dir", type=str, required=True, help="输出目录")
    parser.add_argument("--start_idx", type=int, required=True, help="分子序号起始值")
    parser.add_argument("--end_idx", type=int, required=True, help="分子序号结束值")
    parser.add_argument("--max_jobs", type=int, default=10, help="允许的最大运行任务数")
    parser.add_argument("--cores", type=int, default=1, help="每个任务使用的核心数")
    parser.add_argument("--user", type=str, required=True, help="用户名")
    parser.add_argument("--structure_nums", type=int, default=10, help="每个分子有多少个结构")
    parser.add_argument("--save_wavefunctions", action='store_true', help="是否保存波函数文件（MOPAC不生成波函数，保留此参数以防将来需要）")
    # 新增模式选择参数： single（单点计算）或 geom（几何优化）
    parser.add_argument("--mode", type=str, choices=["single", "geom"], required=True, help="选择计算模式：single（单点计算）或 geom（几何优化）")
    # 新增是否生成几何优化过程帧参数（仅对几何优化模式有效）
    parser.add_argument("--geom_frames", action='store_true', help="是否生成几何优化过程帧（仅对几何优化模式有效）")
    args = parser.parse_args()

    logging.basicConfig(
        filename=f'compute_charge_{args.start_idx}_{args.end_idx}.log',
        filemode='a',
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
    )

    # 计算 RT：室温热能量，单位 kcal/mol（注意此处乘以 1000 是为了转换单位）
    RT_value = (8.314 * 298) / (4.18 * 1000)

    main(
        xyz_directory=args.xyz_dir,
        output_directory=args.output_dir,
        start_idx=args.start_idx,
        end_idx=args.end_idx,
        max_jobs=args.max_jobs,
        cores=args.cores,
        user=args.user,
        structure_nums=args.structure_nums,
        mode=args.mode,
        geom_frames=args.geom_frames,
        save_wavefunctions=args.save_wavefunctions
    )
