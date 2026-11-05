# SamplingIndex 的 metadata SQLite cache

日期：2026-10-26（Asia/Shanghai）。隔离树 `MFM_model_v3_sampling_cache`，分支 `model-v3-sampling-cache`，基线实际 A commit `8c6db4cdc6ea52511fed009ef59d88f3e2c64d8e`。

当前状态：**第一版实现和测试源码已准备，尚未实际运行**。本子 agent 未运行 Python、pytest、SSH、计算任务或 Git 提交。仅新增独立模块、独立测试和本报告，未修改已冻结 A 三文件、旧 sampler、v3_data、factory、公共 contract、数据线或旧证据。

## 解决的问题与明确边界

候选 typed bridge 的 4096 molecule / 65536 conformer 内存边界适合 fixture，不能冒充 24 万代理或百万分子索引。新 `phase1/v3_sampling_cache.py` 接受通用 SamplingIndex 协议，流式写模型自有 metadata SQLite，再提供只读随机访问。它不要求输入是 A 的 Python tuple，也不尝试绕过 A 的候选界限；未来真实 D5 的有界 source adapter 仍需正式接口与权威交付。

缓存只白名单保存 MoleculeEntry/ConformerRef：分子 ID、各 ref 的来源 locator、固定顺序、多样性顺序、原子数、group/family masks、逐分子 mixed 来源、最低能 ID；另保存原身份/采样 hints 与必要 native 五字段 sidecar。不读取或存储标签、坐标、科学数值、原始 LMDB payload。source 物理文件由既有只读 source 实现负责，本 writer 只在新的自有目标目录写文件。

SQLite 是模型工程缓存格式，**不是 D1/D5 release schema**。缓存 COMPLETE 只表示该缓存完整，不授予数据科学冻结状态。真实 D1/D2、D3/D4/D5/D6 与正式训练未由本模块验收。

## API 与流式性

```python
receipt = write_sampling_cache(
    source, fresh_directory,
    expected_source_content_sha256=source.content_sha256,
    batch_rows=512, max_entry_bytes=16 * 1024**2,
)
index = open_sampling_cache(
    fresh_directory,
    expected_manifest_sha256=receipt["manifest_sha256"],
    expected_source_content_sha256=receipt["source_content_sha256"],
)
```

writer 只读取 len(source)、小型标量身份/已存在的 sampler hints，以及逐次 source.molecule_at(i)。不访问 source.molecules、source.bindings 或整个源 dataclass，不在 Python 中汇集所有分子/ID。SQLite unique constraint 承担全局 molecule/native ID 重复检测；每分子验证/编码后立即写入，每 512 分子提交。writer SQLite page cache 明确上限 8 MiB，每条编码有显式 16 MiB 边界；超界失败，不截断数据。总分子数无候选 4k 上限。

按 ordinal 的 INTEGER PRIMARY KEY 查单行，数据库查找 O(log N)，然后只重建该分子本身的 typed metadata。不会把整库恢复为 Python manifest。元数据查询的代价随该分子的构象数变化，不宣称逐分子 JSON 重建为严格常数时间。

输入 content_sha256/role/authority/version/len 及小型 status/hints 在写前后复核；变动导致失败。若一个 source 自行把 content_sha256 实现成 O(N) 计算，缓存无法替它保证该属性的复杂度；可扩展 source 应提供已绑定、可常数读取的身份摘要。

## 三类指纹与恢复保真

reader.content_sha256 **精确保留 source.content_sha256**，reader.version、role、authority 及已有 status/final flags 原值保留。因此原 UniformMoleculeSampler 的 index/版本/配置契约不因缓存路径或存储格式改变，已提交 cursor 与未消费预取可逐位重放。

另行保存并固定：实际 metadata/native 流摘要、数据库字节数/逐字节 SHA256、cache schema/实现源 SHA、COMPLETE manifest SHA。读取必须有 caller 的 manifest pin 和原 source-content pin，不能只相信目录中自称的 version。**cache digest 不冒充源 D5 身份**；源摘要的权威性仍来自原 source 及其已绑定上游，不会凭缓存反向证明最终人口/科学定义。

source 的 geometry_source/ConformationSelection hints 若存在则原样保存，index.make_sampler 使用这些绑定；不一致 override 会拒绝。没有 hints 时 caller 必须显式提供 selection/source。缓存不选择最终不足 k 策略，不重新排序、改最小能量或裁剪原 ref 集合；旧 sampler/commit/load_state_dict 原文件未改。

## native audit 与来源边界

若 source 提供 A 的 native_identity_for，writer 对缓存条目中的**全部构象 ref（在 k 筛选之前）**逐条读取、验证并保存原五字段，原 PM7/UFF 边界保持。reader 提供同名查询，返回原 NativeConformerIdentity，其 as_dict()/canonical content_sha256 与 A 一致。

manifest 明确 native_identity_scope=`sampleable_conformers_only`，表示缓存条目所选来源的全部 ref，不是源 A 未选来源的全审计副本。未缓存来源的 ID 查询抛 KeyError，不假装已保留。五字段 source/ID/分子不一致或缺少本应提供的审计会使 writer 失败，而不是静默丢弃。

没有 native API 的 source 使用基础 reader，**不暴露** native_identity_for，避免 wire provider 把不存在的审计误认为已提供。native row 与 molecule row 的 checksum 独立，原始 nullable UFF provenance 和非连续构象 ID 不补齐、不 remap。

## 完整性、复制与 worker

目标目录必须全新，不覆盖现有缓存。数据库初始 WRITING；全部写入、source 身份复核、SQLite integrity_check 与计数/约束检查通过后才置 COMPLETE、关闭 DB。绑定数据库 SHA 的 COMPLETE.json 最后原子发布并 fsync。失败留下 partial/WRITING/未发布目录，reader 拒绝，不删除源或故障证据。

独立 open 完整核对 manifest/source pins、DB bytes/SHA、SQLite application/schema/version、header 和计数；复制到另一目录/节点后必须重新独立 open。manifest 只引用相对 DB 名，无原目录路径参与 sampler 身份，因此原样复制后仍可恢复原 sampler state。

同节点父进程验证后形成 host/device/inode/size/mtime/ctime receipt。reader pickle 只含路径、pins、小 manifest 和 receipt，不含连接或所有记录。spawn worker 按 PID 懒开 mode=ro/immutable=1/query_only 连接；复核 receipt/小 manifest/schema，逐行验证 payload SHA，不重复扫描全 DB 或 count(*)。独立 open 仍必须全库 SHA；不同 host 或变动 stat 要求重新验证，不把旧 receipt 当永久豁免。

原生 SQLite 句柄在显式 close、上下文退出及 worker Finalize 中关闭；PID 改变时先关闭继承句柄再新开。真实 cache 文件位置是否节点本地由 Root 的运行/分发入口验证，接口不凭一个布尔属性自称已完成真实节点分发。

## 测试源码（尚未执行）

新 `current/tests/test_model_v3_sampling_cache.py` 静态预计 **31 项 CPU 测试**：

1. Lazy source 禁止访问 molecules/bindings/labels/coordinates，64 与 8192 分子流式写入；source weakref 活对象峰值要求 ≤2，读对象 pickle <8 KiB 且大小不随全体记录复制。这验证对象流式性，不冒充已测真实百万规模 RSS/吞吐。
2. 复制目录后重开，PM7/UFF/mixed refs、顺序、原子数、masks、energy minimum、authority/role/version、native 五字段/canonical SHA 与源一致；原 sampler checkpoint 与预取 draw 逐位一致，RNG 不变。
3. 实际固定 SHA `50aceee7…` DataB 纯投影→冻结 A typed index→SQLite→原 sampler；k=1 时 native sidecar 仍保存所选来源全部三个构象，未选来源的 omission scope 明确。
4. 独立 open 一次 DB SHA；关闭后同节点 receipt 重开不重扫。模拟 PID ownership 改变验证旧句柄实际关闭。
5. 真正两个 spawn worker，通过 barrier 确保两 PID 实际参与；禁止 worker 全库 SHA，实际尝试写入被拒绝，逐个 SQLite 句柄 close 后查询失败，所有 worker join 退出。
6. 中断、源身份变化、重复分子、错 source pin、既有目录、越界/非法 ordinal、WRITING、数据库损坏、schema/计数/pin 错误、行 SHA/ordinal/native identity 不一致、stale receipt、entry 边界与无效 typed 原子数均拒绝并保留原自有 fixture。变体只改新复制的负例目录，原缓存保留。

建议 Root 在受控 Slurm CPU/依赖/源码前后验证下执行：

```bash
PYTHONPATH=current:$PYTHONPATH /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m pytest \
  current/tests/test_model_v3_sampling_cache.py \
  current/tests/test_model_v3_sampling_bridge.py \
  current/tests/test_model_v3_labels.py -q
```

还需完整 premerge/checker/postmerge。以上为预计覆盖，没有实际测试结果；真实 24 万/百万分子读取吞吐、节点缓存分发、真实 provider/D5 权威和最终训练入口仍需对应数据交付及运行期验收。

## 准备版本来源

- 新 `phase1/v3_sampling_cache.py`：SHA256 `25ad189b9bdb5bde75b22690e7b886c12308ad5b0e6ff501c88b8c2dfb0f57cd`。
- 新 `current/tests/test_model_v3_sampling_cache.py`：SHA256 `efaa3d3b4ecf7cceba6a26e770542dfa4b1bcac217e43e84529a997ed40587e5`。
- 未改 A bridge：SHA256 `2c15a8b61fa5b071d3e64cd8f769a8e43930174dbaa0555e70a1ef233809d946`。
- 未改旧 sampler：SHA256 `031c387f60697f7b8d0ba1bc38ed64bb08664fddbd00a7a425c597171aac04f8`。

源码 hash 绑定本次准备版本，不借用旧单元/回归通过声明；Root 的实际 Slurm/源码/日志结果应另行记录。
