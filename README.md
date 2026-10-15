# MFM 开发仓库

分子共享主干模型、数据生成与加载、下游微调和推理的开发代码。2026-10-16 从当前服务器工作整理；只提交代码、配置、接口说明和来源清单。权重、真实数据、队列、embedding、训练日志及计算归档保留在外部存储。

**新开发从 [开发交接文档](docs/DEVELOPMENT_HANDOFF.md) 开始。** [数据接口](docs/DATA_PIPELINE.md) 说明最终训练输入与生成产物的区别；[验证记录](docs/VALIDATION.md) 说明此次检查范围。

| 目录/入口 | 内容 |
| --- | --- |
| `current/phychem_mfm/` | 最新 S 实验实际绑定的 Stage59 模型、数据层、训练与微调核心 |
| `current/scripts/`、`current/tools/` | 预训练、冻结 H0 探针、审计、统计与实验管理 |
| `workflows/sprime_s/` | S′ 构象生成、S-only 原生数据加载和收敛实验 |
| `workflows/wp5/` | PM7/xTB 标签生成、解析、float64 导出、恢复与验收 |
| `workflows/dataset_rebuild/`、`workflows/screening/` | 数据筛查、几何分析和原生解析器 |
| `workflows/phase1_downstream/` | 五套下游数据的绑定、微调/读出和预测评价 |
| `tools/encode_h0.py` | 可移植的 XYZ → 原子/分子 H0 推理入口 |
| `tools/check_repository.py` | 源码 SHA、语法、重资产及凭据检查 |
| `reproduction/linked_sources/` | 冻结实验引用的原生 transport 与科学协议 |
| `legacy/descriptor/` | 历史 descriptor 版本，含 ADMET 微调、CV 预测和集成推理 |
| 根目录 `models/`、`pretrain/`、`dataset_*.py` | 仓库原有 MoE 版本；说明见 [旧 README](docs/LEGACY_ROOT_README.md) |

## 安装与检查

Python ≥3.10；推荐 Linux。先安装与目标硬件匹配的 PyTorch，再安装模型包和数据工具依赖：

```bash
git clone https://github.com/mint258/MFM.git
cd MFM
python -m pip install -r requirements-dev.txt
python tools/check_repository.py
python current/scripts/train.py --help
python tools/encode_h0.py --help
```

`current/requirements.txt` 是原模型包依赖；根目录原 `requirements.txt` 属于历史 MoE。服务器实际版本见 `docs/SERVER_ENVIRONMENT.json`，CUDA 兼容性在目标节点核验。

## 当前模型与推理

下游统一使用 `SharedBackboneMFM.encode_atoms(batch)` 的 H0；分子表示从 H0 池化。最新 S 实验为 shared-light、384 维、4 层、6 个注意力头；参数以 `workflows/sprime_s/formal_s/*_v2.json` 为准。

```bash
python tools/encode_h0.py \
  --checkpoint /external/checkpoints/segment_final.pt \
  --configuration workflows/sprime_s/formal_s/B3_seed0_v2.json \
  --xyz-root /external/xyz \
  --output /external/outputs/h0.npz --device cpu --limit 10
```

S checkpoint 的 configuration 必须为训练时的原始 JSON，SHA 必须匹配。普通训练 checkpoint 的 `model_state/model_config` 格式不需要此参数。输出含 `atom_h0`、`graph_h0`、`graph_ptr` 和文件路径；性质预测还需匹配的下游读出模型。

## 开发与原实验复现

`current/` 和可移植工具用于新开发；`workflows/` 保留原实验版本、服务器路径与校验约束。正式入口依赖外部数据、manifest、环境和资源分配，不能仅凭克隆仓库复现整个实验。最新入口和前置条件见交接文档。

源码保留原字节，来源/SHA 见 [SOURCE_MANIFEST.json](docs/SOURCE_MANIFEST.json)。新推理工具与检查器位于冻结包外，不改变服务器上的科学源码。