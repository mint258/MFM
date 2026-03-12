#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMILES ➜ 3D XYZ · Open Babel 3 版
-------------------------------------------------
• 多构象 + 加氢 + 写入净电荷与 SMILES
• obabel 调用支持超时 (默认 30 s)
• 若目标 XYZ 已存在：已满→跳过；缺口→仅补齐
-------------------------------------------------
"""

import argparse, logging, random, subprocess
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import multiprocessing as mp
from openbabel import openbabel as ob

random.seed(42)

# ---------- 构象数选择 ----------
def need_confs(n_atoms: int) -> int:
    return 1 if n_atoms < 5 else 5 if n_atoms <= 20 else 10

# ---------- 单分子处理 ----------
def process(idx: int, smi: str, tmpdir: Path, outdir: Path, timeout: int):
    """
    若 principal_{idx}_{01..n_conf}.xyz 已全在 outdir 中 → 直接返回。
    否则只为缺失的 conf_idx 生成 XYZ。
    """
    # 解析 SMILES 获取总电荷 & 需要的构象数
    conv = ob.OBConversion(); conv.SetInFormat("smi")
    mol = ob.OBMol()
    if not conv.ReadString(mol, smi):
        raise RuntimeError("Open Babel 无法解析 SMILES")
    total_charge = mol.GetTotalCharge()
    n_conf = need_confs(mol.NumAtoms())

    # 统计已有 / 缺失构象
    miss_conf = [c for c in range(1, n_conf + 1)
                 if not (outdir / f"principal_{idx:08d}_{c:02d}.xyz").exists()]
    if not miss_conf:                       # 已经齐全，直接跳过
        return

    # 仅为缺失构象调用 obabel
    for conf_idx in miss_conf:
        outxyz_tmp = tmpdir / f"principal_{idx:08d}_{conf_idx:02d}.xyz"
        cmd = ["obabel", f"-:{smi}", "-O", str(outxyz_tmp), "--gen3d", "-h"]

        try:
            subprocess.run(cmd, check=True, timeout=timeout,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"obabel 超时 > {timeout}s")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"obabel 失败，返回码 {e.returncode}")

        # 重新写 XYZ
        lines = outxyz_tmp.read_text().splitlines()
        try:
            atom_count = int(lines[0].strip())
        except ValueError:
            raise RuntimeError("XYZ 首行原子数解析失败")

        new_txt = [f"{atom_count}\n", f"{total_charge}\n"]
        new_txt += [l.rstrip() + "\n" for l in lines[2:2 + atom_count]]
        new_txt.append(smi + "\n")
        outxyz_tmp.write_text("".join(new_txt))

# ---------- worker ----------
def worker(args):
    idx, smi, tmpdir, outdir, timeout = args
    try:
        process(idx, smi, tmpdir, outdir, timeout)
        return True, idx, smi
    except Exception as e:
        logging.warning(f"[worker] idx={idx}: {e}")
        return False, idx, smi

# ---------- 主函数 ----------
def main(csv_path: Path, outdir: Path,
         start, end, timeout, nproc):
    outdir.mkdir(parents=True, exist_ok=True)
    tmp = outdir / "_tmp";  tmp.mkdir(exist_ok=True)

    df = pd.read_csv(csv_path)
    smiles = list(enumerate(df.iloc[:, 1], 1))
    sel = [(i, str(s), tmp, outdir, timeout) for i, s in smiles
           if (not start or i >= start) and (not end or i <= end)]

    with mp.Pool(processes=nproc) as pool:
        for ok, idx, smi in tqdm(pool.imap_unordered(worker, sel),
                                 total=len(sel), desc="build"):
            if not ok:
                (outdir / "failed.log").open("a").write(f"{idx},{smi}\n")

    # 搬运 tmp ➜ outdir（避免覆盖）
    for xyz in tmp.glob("*.xyz"):
        target = outdir / xyz.name
        if not target.exists():
            xyz.rename(target)
        else:
            xyz.unlink()
    tmp.rmdir()

# ---------- CLI ----------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv",    required=True, help="CSV（第二列为 SMILES）")
    ap.add_argument("--outdir", required=True, help="XYZ 输出目录")
    ap.add_argument("--start",  type=int,      help="起始行号")
    ap.add_argument("--end",    type=int,      help="结束行号")
    ap.add_argument("--timeout",type=int, default=30, help="obabel 超时(s)")
    ap.add_argument("--nproc",  type=int, default=16, help="并行进程数")
    args = ap.parse_args()

    logging.basicConfig(filename="obabel_xyz_timeout.log",
                        level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    main(Path(args.csv), Path(args.outdir),
         args.start, args.end, args.timeout, args.nproc)
