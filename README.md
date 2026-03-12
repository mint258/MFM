# MFM Repository

本仓库当前围绕三个主目录组织：

- `dataset/`：原始 xyz 读取、LMDB 构建、RDKit descriptor 生成与样本检查
- `pretrain/`：扰动建模、数据装载、训练循环、W&B 记录与训练主流程
- `models/`：MoE backbone / expert / multitask head

历史脚本、旧模型和根目录遗留数据脚本已备份到 `waste/`。

## 目录结构

```text
MFM_repository/
├─ dataset/
│  ├─ build_lmdb.py
│  ├─ dataset_lmdb.py
│  ├─ dataset_without_charge.py
│  ├─ dataset_infer.py
│  ├─ rdkit_descriptor_generator.py
│  ├─ descriptor_schema.py
│  └─ RDKIT_DESCRIPTOR_RECORD.md
├─ pretrain/
│  ├─ args.py
│  ├─ data.py
│  ├─ degrade_molecules.py
│  ├─ geometry.py
│  ├─ train_loop.py
│  ├─ pipeline.py
│  ├─ checkpoint.py
│  ├─ utils.py
│  ├─ utils_debug.py
│  └─ wandb_utils.py
├─ models/
│  └─ moe/
├─ test_data/
├─ test_ckpt/
├─ wandb/
└─ waste/
```

## 环境

建议使用 `chemprop` 环境：

```bash
conda activate chemprop
```

## 数据构建

从 xyz 构建 LMDB：

```bash
python -m dataset.build_lmdb --raw_roots <raw_xyz_dir> --stable_roots <opt_xyz_dir> --with_rdkit_descriptors
```

检查单个 LMDB 样本：

```bash
python -m dataset.inspect_lmdb_sample --lmdb_path <data.lmdb> --index 0
```

## 预训练

主入口：

```bash
python -m pretrain.pipeline --data_roots <data.lmdb> --epochs 10 --batch_size 4
```

当前多任务头包含：

- `energy` 分支：能量 + 全部 graph-level RDKit descriptors
- `charge` 分支：部分电荷 + `formal_charge` / `donor` / `acceptor` / `EState_index`
- `element` 分支：元素重建 + 其余 node-level RDKit descriptors
- `geom` 分支：几何重建

新增 loss 系数：

- `--lambda_e_desc`
- `--lambda_q_desc`
- `--lambda_z_desc`

示例：

```bash
python -m pretrain.pipeline \
  --data_roots test_data/principal_valid_test.lmdb \
  --epochs 2 \
  --batch_size 4 \
  --lambda_e 1.0 --lambda_e_desc 0.5 \
  --lambda_q 1.0 --lambda_q_desc 0.5 \
  --lambda_z 1.0 --lambda_z_desc 0.5 \
  --use_wandb --wandb_mode offline
```

## W&B

- `train/batch/*` 记录 batch 级聚合 loss
- `train/epoch/*` 与 `val/*` 记录 base task loss、descriptor 聚合 loss，以及每个 descriptor 的细项 loss / metric
- `--wandb_mode offline` 可用于本地验证，不上传线上

## 其他

- 扰动样本工具：`python -m pretrain.degrade_molecules --help`
- 旧脚本与废弃内容：`waste/`
