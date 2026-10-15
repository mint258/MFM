# MFM 开发交接

2026-10-16（Asia/Shanghai），目标仓库 `mint258/MFM`。

## 来源与版本

最新 S 实验实际导入 `/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime`，因此 `current/` 保存该实际绑定版本的包、脚本、测试和配置。较早的独立重构主目录为 `/share/home/zixiao/PhyChem_MFM_ICLR2027`。

S runner v8 SHA 为 `ee8063cda7f33b80b136bfec436062abef9319cb40554bf9f1ba6616798f6b71`。Stage59 原科学协议收入 `reproduction/linked_sources/`；Phase1 和 WP5 科学要求原文在 `docs/protocols/`。导出文件逐条原路径/字节数/SHA256 见 `SOURCE_MANIFEST.json`。原配置的路径与校验值保持原样。

根目录的原 MoE 文件保留原 Git 历史；`legacy/descriptor/` 保存服务器 descriptor 扩展与历史 ADMET 入口。新开发从 `current/phychem_mfm` 开始，不同时加入历史同名模块目录。`tools/encode_h0.py` 和仓库检查器是本次新增工具，位于冻结包外。

## 代码入口

| 工作 | 文件/API |
| --- | --- |
| 创建模型 | `current/phychem_mfm/factory.py` → `build_model(config)` |
| 共享主干/预测头 | `model/shared.py`、`backbone.py`、`attention.py`、`heads.py` |
| 原子/分子表示 | `SharedBackboneMFM.encode_atoms(batch)`、`encode_graph(batch, pooling)` |
| LMDB 单分片 | `current/phychem_mfm/data/dataset_lmdb.py` → `LmdbMoleculeDataset` |
| XYZ 推理数据 | `current/phychem_mfm/data/dataset_infer.py` → `MoleculeDataset` |
| 完整训练数据与预取 | `phase1/full_corpus_loader.py` → `CompactNativeIndex`、`FullCorpusViewsDataset`、`BlockAtomBatchSampler`、`make_prefetch_loader` |
| 最新 S 数据加载 | `workflows/sprime_s/scripts/s_native_adapter_v2.py`；依赖 v1 |
| 通用训练 CLI | `current/scripts/train.py`；先查看 `--help` |
| 完整语料训练 | `current/scripts/train_phase1_full_corpus.py`；需要冻结数据/协议/归一化/初始化 |
| 最新 S 训练 | `workflows/sprime_s/scripts/s_convergence_runner_v8.py`；原 B1/B3 配置 |
| 下游微调核心 | `phase1/downstream_training.py` → `DownstreamTrainBatch`、`DownstreamTrainer` |
| 下游预测头 | `phase1/downstream_readout.py` → `SourceAlignedH0Readout`、`SourceAlignedLinearGraphReadout` |
| 正式下游 worker | `workflows/phase1_downstream/stage60_full_downstream_runner_v1/run_formal_readout.py` |
| 下游数据 provider | `workflows/phase1_downstream/stage60_downstream_binding_v3/downstream_binding_data.py` → `FrozenDownstreamStore` |
| 可移植推理 CLI | `tools/encode_h0.py`；外部 XYZ/checkpoint → H0 npz |
| 最新 S 终点 H0 | `workflows/sprime_s/scripts/extract_s_probe_h0_v2.py` |
| 最新线性探针 | `workflows/sprime_s/scripts/run_s_linear_probes_v2.py`；协议 `configs/s_probe_protocol_v2.json` |
| 历史 ADMET 微调/预测 | `legacy/descriptor/admet/train.py`、`predict_CV.py`、`ensemble.py`，说明见同目录 `USAGE.md` |

表中 `model/`、`phase1/` 相对 `current/phychem_mfm/`。微调核心是一个 API，支持 frozen/finetune、显式目标/掩码、W&B 和恢复。`current/tests/test_phase1_downstream_training.py` 展示完整 batch/config 和恢复调用；正式 readout worker 展示真实数据调用。测试 synthetic tracker 不可代替正式实验记录。

最新 S 模型为 shared-light、384 维、4 层、6 heads、119 元素/遮蔽类型、残差几何头；sampler 上限为512分子/65536原生原子/8000000 padded-cost。`s_model_memory_v1.py` 的距离 MLP 分块保留参数和 state-dict 键；H0 推理无需训练期补丁。旧 ADMET 模型和当前 S 权重有不同格式，不能直接互换。

## 安装与接手检查

Linux/Python ≥3.10；先安装与硬件匹配的 PyTorch，再执行：

```bash
python -m pip install -r requirements-dev.txt
python tools/check_repository.py
python tools/check_repository.py --verify-export
python tools/encode_h0.py --help
python current/scripts/train.py --help
```

`SERVER_ENVIRONMENT.json` 记录本次 CPU 检查环境及额外依赖路径，不代表所有正式 GPU 运行环境。原 requirements 的宽松下限不等于验证过的 CUDA 环境。MOPAC/xTB 二进制与精确运行环境通过外部复现包核对。

核心测试示例：

```bash
export PHASE1_NATIVE_TRANSPORT_PATH="$(pwd)/reproduction/linked_sources/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py"
cd current
python -m pytest tests/test_encoder_api.py tests/test_dataset_parity.py \
  tests/test_phase1_full_corpus_loader.py tests/test_phase1_downstream_training.py -q
```

本次实际验证结果见 `VALIDATION.md`。部分其他测试依赖真实 LMDB 或固定服务器布局；语法检查不等于科学流程验收。

## 数据与外部依赖

详见 `DATA_PIPELINE.md`。WP5 输出是12类计算的 float64 family parquet 与审计归档；S′ 输出是构象 parquet。最终训练还需要外部原 LMDB、角色/人口索引、原子数文件、transport、TRAIN-only 归一化和初始化。

本次未建立 `lmdb_1`、未向原 LMDB 回写新字段。已有 loader 可消费其声明的最终训练输入；不能把 WP5 parquet 直接传给 LMDB loader。新标签整合格式需要下一阶段明确 schema 并验证映射。

## 服务器路径与复现

| 用途 | 外部路径 |
| --- | --- |
| 工作工程 | `/share/home/zixiao/descriptor_analysis` |
| 本次实际模型包 | `/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime` |
| 原训练数据 | `/share/home/zixiao/dataset/lmdb_new` 及配置中的其他只读 shard |
| WP5 数据/队列/验收 | `descriptor_analysis/runs/phase1_wp5_20261011` |
| S′/S 生成/训练/探针 | `descriptor_analysis/runs/sprime_s_convergence_20261013` |
| 本次导出与检查 | `descriptor_analysis/docs/github_export_20261016` |

Windows `X:\` 为实时 SSHFS；本地 Git checkout 是明确导出副本，不自动双向同步。服务器 Linux 命令通过 `ssh descriptor-analysis-remote` 后进入 `compute-0-20`；实际服务器编辑在 `X:\`，遵循安装的 HPC skill 和项目规范。

`workflows/` 包含原路径、UID、hostname、Slurm、数据身份和源 SHA 绑定。恢复原实验须保有配套外部数据/证据。迁移新机器时建立新的显式路径配置和来源绑定，验证后使用新的输出根；不要覆写原队列、协议、checkpoint 或历史验收，也不要批量执行历史 sbatch/恢复/清理脚本。

正式计算使用站点既有 sbatch/partition/account 流程，核验真实资源与 GPU UUID；正式训练使用持久 W&B，offline 后同步。付费学校服务器仅用于用户明确批准的正式预训练。密码、私钥、API key 不进入仓库。

## 状态与科学边界

原服务器最新 S′/S 状态为 `FULL_EXPERIMENT_ACCEPTED`：两个 B1 各完整一轮，B3 完整三轮、七个 H0 端点；结论是一轮不足。它不代表其他矩阵或 WP5 最终数据全部完成。本次只导出代码并验证，没有启动新训练/QM/数据生成，也没有变更并行任务状态。活动进度以服务器当前 README/交接和实际 acceptance 为准。

PM7 能量是 FINAL HEAT OF FORMATION（kcal/mol），电荷是 NET ATOMIC CHARGES（e），坐标为 Å。训练/归一化只用 TRAIN。ExpansionRx 保留官方5326 TRAIN/2282 TEST；最新探针35报告项、32主项，QM9 A/B/C为辅助。保留原子身份、任务掩码和官方划分。

后续修改在开发分支完成，运行相关测试与默认仓库检查。`--verify-export` 仅用于核对本次原始导出字节，开发修改后可能不再通过；默认检查继续检查语法、大小和凭据。原 `SOURCE_MANIFEST` 用于历史追溯；新源版本另外记录，不能把新代码 SHA 填进旧科学验收。GitHub 的 Source checks workflow 自动执行默认检查。重资产持续保存在外部，通过小型配置/身份清单说明依赖。
