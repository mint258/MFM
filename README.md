# MFM Repository

本仓库用于分子多任务预训练与推理，包含：
- 多任务 MoE 模型（能量、部分电荷、元素类别、几何坐标）
- 预训练流程（数据构建、扰动建模、分阶段训练、损失计算）
- 推理脚本与测试数据

## 目录结构

```text
MFM_repository/
├─ models/
│  └─ moe/
│     ├─ common.py          # 线性层初始化、基础工具
│     ├─ attention.py       # 稠密几何注意力与 Transformer 层
│     ├─ backbone.py        # 实坐标 Backbone
│     ├─ expert_blocks.py   # 专家块（real/internal）
│     ├─ multitask.py       # MultiTaskMoE 主模型
│     └─ __init__.py
├─ pretrain/
│  ├─ args.py               # 预训练 CLI 参数
│  ├─ data.py               # 数据集封装、扰动数据集、标准化采样
│  ├─ geometry.py           # 几何索引与几何损失工具
│  ├─ train_loop.py         # run_epoch 与训练统计
│  ├─ checkpoint.py         # checkpoint 保存
│  ├─ utils.py              # seed、scheduler 等工具
│  └─ pipeline.py           # 训练主流程
├─ pretrain_multitask.py    # 兼容入口（仍可直接执行）
├─ moe_transformer_multitask.py  # 兼容导入层
├─ structure_predict.py     # 推理脚本
├─ dataset_*.py             # 数据集读取脚本
├─ degrade_molecules.py     # 扰动生成工具
├─ test_data/               # 测试数据
└─ test_ckpt/               # 本地测试权重（不建议提交）
```

## 环境

建议使用 `chemprop` 环境：

```bash
conda activate chemprop
```

如果缺少依赖，请在该环境中安装（如 `torch`, `torch-geometric`, `torch-cluster`, `scikit-learn`, `tqdm`）。

## 预训练用法

### 兼容入口

以下命令保持可用：

```bash
nohup python pretrain_multitask.py --data_roots ../../../dataset/principal_test.lmdb --batch_size 4 --stage1_max_epochs 2 --stage2_loss 0.01 --morse_a 0.6 --lambda_dist 1 --lambda_coord 0 --lambda_angle 2 --lambda_torsion 4 --lambda_planar 0 --lambda_e 5 --lambda_q 1 --lambda_z 0.01 --loss_cutoff 2 --expert_number_E 1 --expert_number_Q 1 --expert_number_Z 1 --expert_number_G 1 --hidden_channels 128 --bb_layers 2 --bb_heads 4 --bb_ff_mult 4 --bb_radius 8.0 --expert_real_layers 2 --expert_int_layers 0 --expert_heads 4 --expert_ff_mult 2 --save_path test_ckpt/real_only_mini/AE_test.pth --epochs 50 --save_every_epoch --num_workers 16 --lr 5e-4 --perturb_mix "geom:0.1@1,geom:0.2@0.4,topo:0.2@0.5,both:0.05@0.3,geom:0@1" --perturb_seed 114 > train_real_only_mini.log &
```

### 主流程入口

也可直接执行：

```bash
python -m pretrain.pipeline --data_roots <your_data.lmdb> --epochs 10 --batch_size 4
```

## 推理用法

```bash
python structure_predict.py --help
```

`structure_predict.py` 会从 checkpoint 的 `cfg` 与 `model_state` 自动恢复 `MultiTaskMoE`。

## 设计说明

- 模型脚本已按“Backbone / Expert / Head”拆分，减少单文件长度，便于维护。
- 预训练脚本已按“参数 / 数据 / 几何 / 训练循环 / 主流程”拆分，便于扩展损失与训练策略。
- 通过兼容入口保留了原有调用方式，降低迁移成本。
