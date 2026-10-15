# 数据生成与最终训练输入

```text
只读原 LMDB + 原分子/构象身份
  → WP0/WP1 筛查、几何核验和泄漏处理
  → WP5 正式人口/角色索引
     ├─ PM7/xTB whole-molecule 计算 → float64 family parquet
     └─ 状态/审计/复现证据 → 验收与交付索引
另：S′ ETKDG/UFF 生成 → float64 构象 parquet + 状态清单

模型实际输入：原 LMDB + 角色索引 + atom-count 文件
  → 原生 label transport + 有界 clean cache
  → 确定性视图/掩码 → atom-budget sampler + spawn 预取
  → PyG batch → 共享 H0 / 监督头
```

WP5/S′ parquet 是生成结果。已验收 S-only 训练读取声明的原 LMDB/native index，不自动将 S′ 构象或所有 WP5 新标签混入训练。

## 生成与导出入口

| 阶段 | 代码 |
| --- | --- |
| 原始数据/几何筛查 | `workflows/dataset_rebuild/scripts/wp0_inventory.py`、`wp1_geometry.py`、`wp1_report.py` |
| 原生字段解析 | `workflows/dataset_rebuild/scripts/wp4_parsers.py`、`workflows/wp5/scripts/wp5_parser.py` |
| WP5 runtime | `workflows/wp5/scripts/wp5_runner_v14.py` |
| WP5 引擎/导出 | `wp5_engine_v2.py`、`wp5_parquet_v2.py`、`wp5_archive_v5.py`；依赖以 frozen contract 为准 |
| WP5 科学合同/字段登记 | `workflows/wp5/configs/protocol.json`、`production_contract_v7.json`、`workflows/screening/registry/label_registry_v2.json` |
| WP5 最终交付 | `wp5_acceptance_catalog.py`、`wp5_acceptance_delivery_v2.py`、`wp5_acceptance_delivery_index_v1.py` |
| S′ 科学生成 | `workflows/sprime_s/scripts/sprime_v6.py` |
| S′ 全人口队列 | `full_dataset_v7.py`、`full_dataset_v8_extra_cpu.py`（追加节点准入版） |
| S′ 闭合 | `finalize_full_v7.py` 及对应随机100重现入口 |
| 最新 S 训练元信息生成 | `workflows/sprime_s/scripts/prepare_s_training_inputs_v1.py` |

表中短文件名相对上方同一 workflow 的 `scripts/`。目录保留历史版本与诊断工具，不能按最高文件名数字猜依赖，也不能批量运行旧提交/恢复/清理工具。

## 已有可用 dataloader

单分片 LMDB 示例：

```python
from phychem_mfm.data.dataset_lmdb import LmdbMoleculeDataset
from torch_geometric.loader import DataLoader

dataset = LmdbMoleculeDataset('/external/data/shard.lmdb', limit=64, strict_index=True)
loader = DataLoader(dataset, batch_size=4, shuffle=False, num_workers=0)
batch = next(iter(loader))
```

LMDB 必须有 `__len__` 和原格式 pickle/PyG 记录。完整数据使用 `CompactNativeIndex`、`FullCorpusViewsDataset`、`BlockAtomBatchSampler` 和 `make_prefetch_loader`。

最新 S loader 使用 `MappedRecordIndex`、`ManifestViewsDataset`、`CountIndex`，依赖外部 `training_inputs_v1/manifest.json`、record_metadata Arrow IPC、little-endian uint32 atom counts、shard snapshot 和原只读 LMDB。实际记录 payload SHA、条数、角色和文件身份必须与配置一致。

多 worker 保持 spawn、各 worker 只读句柄、有界缓存、有限等待、退出 close/join；恢复只使用已消费游标。输入结构为 `x`（Z-1）、`pos`（Å）、`batch`、`ptr`。H0 不接收目标标签；缺标签通过 mask 标示，不能用零替代。下游另显式携带源原子编号、候选/监督掩码和 output-level。

## 重资产与尚未执行的整合

外部提供原 LMDB、真实 XYZ/SMILES/下游数据、人口 parquet、queue SQLite、family parquet、S′ 构象、Arrow/memmap 索引、归一化/初始化、checkpoint 和 H0 cache。仓库提供生成器、解析器、schema、消费接口和身份校验代码。原生 transport 已收入 `reproduction/linked_sources/.../native_qa_stats_v3.py`；MOPAC/xTB 软件和 W&B 历史通过外部环境/复现包取得。

本仓库不包含新建并验收的 `lmdb_1`。把 WP5 新标签整合成下一阶段最终训练格式，需要确定字段/schema、记录与原子映射、精度/缺失掩码，并完成读回和新 manifest 验证。已有 LMDB/S loader 的可用性不代表该尚未执行的整合已经完成。
