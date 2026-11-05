# D-1 v3.1：第 6 项存储格式修订

2026-11-05，用户已授权实施。本修订只替换 `training_format_v3.md` 第 6 项的存储约定；其余科学语义沿用已共同冻结的 D-1 v3.0 及实际 D-2/D-4/D-5。v3.0 原文、数据及 GPU 副本保留。模型线对本格式的确认和实际加载/逐头验收仍待完成，导出不等待确认。r73 下述紧凑数值扩展已经用户单独批准。

## 6. MFM4 紧凑存储

同一试点 50,000 TRAIN 与 5,000 ROUTINE VAL。每划分一个 LMDB 目录 `v31_pilot_TRAIN/`、`v31_pilot_VAL/`，只用默认数据库。两者共用根目录 `schema.json`；各目录含 `manifest.json`、`id_map.parquet`。ID 映射保留 molecule_id、native_record_id、原 S′ 索引及必要的可逆原子重排；记录中不存这些字符串。

键为大端 `M+uint32(molecule_index)`，或 `P/U+uint32(molecule_index)+uint16(conformer_index)`。两个划分各自分子序号从零连续编号，各分子来源内构象序号从零连续编号。已有 fixed_random、energy、diversity 通过分子记录的 uint16 排列保存；未发布的顺序不伪造。

值头为 `MFM4` 四字节魔数、小端 uint16 格式版本 1、小端 uint16 数组数。每个数组写 uint16 ID、uint8 dtype 码、uint8 ndim、ndim 个小端 uint32 尺寸、C 连续小端原始数组；每个数组 raw 末尾补零至四字节边界。scalar ndim=0。dtype 码 1=u1、2=i2、3=u2、4=u4、5=i4、6=f4。无 JSON、字符串、路径、哈希、pickle 或 object。

分子 M 存 Z:u1[N]、bonds:i2[E,2]、bond_order:u1[E]、原始 d20:f4[F_D20]、role:u1、来源构象数:u2[2]、已有来源排列:u2[]、两来源 D-5 holdout:u1[]。分子图每分子保存一次。D-5 留出基底及其原标签存入相应 P/U，holdout 标记控制训练排除；不改变既有 D-5 清单或子集。

PM7 P 存 pos:f4[N,3]、实际 pos_perturbed:f4[N,3]、mol_labels:f4[F_mol]、atom_labels:f4[N,F_atom]、atom_vectors:f4[N,F_vec,3]、pair_index:i2[J,2]、pair_labels:f4[J,F_pair]。分子矢量与张量按原注册表/成员顺序展开。全部原子对字段共享一次有向端点并集，字段缺少的并集行用 NaN，不做镜像、求和或改变物理方向。11 份重复的程序输入几何不再各占一条记录，原身份可由 ID 映射连接。

r73 是原有有序多通道条目，不能缩成普通 pair 单值。用户批准其四个扩展数组：31 `r73_pair_row`:u4[K] 引用同一 pair_index；32 `r73_channel_codes`:u2[K,3] 保存 basis_i、basis_j、可选 channel 的整数码；33 `r73_onsite`:u1[K]，0=未提供、1=false、2=true；34 `r73_values`:f4[K]。通道字典仅在 schema 中一次定义，码 0 表示缺席，空字符串有自己的非零码。K 的行顺序就是原条目顺序，保留重复、自环及方向，不存 UTF-8、offset、ordinal 数组。

UFF U 当前仅存 pos:f4[N,3]；这次旧 D-3/D-5 输入不含 UFF D′/P′ 标签。以后加入 P′ 可沿用 P 的标签数组布局，不借用本轮 PM7 标签。

所有源 invalid/missing/masked 分量写 NaN，加载器以 isnan 得到数值掩码。不存另一个掩码数组；LOSS_DISABLED 不等于数值 invalid，其原有效数值照存、在 schema 禁 loss。只保存原始数值，不做归一化；加载器按同一 D-4 执行。r674 仍 LOSS_DISABLED。原科学精度权威为 WP5 float64 Parquet，不新增 F64 副本；ID 映射与既有输入 Parquet 清单提供恢复路径。

schema 定义数组、每列真实字段/家族/标签组/层级/单位/广延或强度属性/损失状态、D-2/D-4/D-5 版本、导出 Git 提交及既有 Parquet SHA 引用。未声明的物理属性标 UNKNOWN，不由存储器推断。

写入 map_size=预估值两倍，空间不足时按实际增长扩展映射，预期体积不是停止门。每划分完整写完后只执行一次 `mdb_copy -c`，共享最终库以 `rsync --sparse` 分发各 GPU 节点。保留 v3.0 与其副本，不试其他压缩方法。

末尾仅一次检查：原子数/拓扑对齐（不同拓扑列清单）、1000 个随机 PM7 构象与原 v3.0 按字段/掩码对照（absΔ≤1e-6+1e-6|x|）、分子和普通来源构象计数一致。旧 D-3 与对应 D-5 的并集是 holdout 照存的对照基准，重复 input view 的合并另列计数，不能冒充丢失构象。无额外读回、独立复核、吞吐或文件/记录 SHA 重算。真正模型验收仍由加载器与逐预测头过拟合执行。

## 与 v3.0 的差异

- 分家族命名子库改为每划分单默认库；字符串身份迁到 ID Parquet。
- MFM3 每记录 JSON/header/trace/hash 与独立 mask 改为 MFM4 数值数组和 NaN。
- 分子图/D20 每分子一次，重复程序几何与 pair 索引去重；r73 以批准的整数码扩展无损保留原条目。
- 不新增 F64 旁车，精度权威回指原 WP5 Parquet；科学数值、字段、角色、原顺序、归一化和 D-5 不变。
- 只执行用户指定的一次末尾检查、一次 LMDB compact copy；分发用 rsync --sparse，不做新吞吐或哈希复核。
交付后存储状态补充（2026-11-05）：用户随后明确授权删除旧D3 v3.0及无用中间产物，清理已完成。上文保留旧v3.0为导出当时要求；当前旧数据已退休，仅保留历史清单。原始native LMDB与WP5 Parquet及当前v3.1未删除，科学格式和字段不变。

## 6. D6 全量存储补充（窗口二任务书 v2）

沿用同一个 MFM4 codec 与数组布局。TRAIN 为最终 Common TRAIN；FULL 保留原 FULL 全体及 Common VAL/ROUTINE。U 现保留其真实几何上的 D3/atomicSASA 和已实际计算的独立 P′，不复制 PM7 标签。D20 仍在 M 每分子共享一次。科学数值权威仍为原 F64 source/typed entries；新增 UFF D3 按真实 native anchor/实际几何只计算一次，其独立 F64 cache 同供统计及导出，MFM4 不新增 F64 旁车。

M 新增数值标记：15=ROUTINE，16=Common，17=aligned-U ordinary S′ membership，18=aligned-U P′ train eligibility。M6 为 addressable P/U 数，不冒充普通 S′ N；普通 U 排列、N 与默认 k-grid 只使用 M17=1 的原科学集合。N1 P′-only、冻结 D5 diagnostic-only、未注册但真实存在的旧 P′ source 几何均可独立 addressable，M17=0；原科学 sprime_conf_idx 不变，同索引不同几何用外部 storage alias 区分。原 source GID 缺失仍标 NULL；`pprime-source:<原record_id>` 仅地址化其实际关闭 F64 source 行，不宣称新增普通构象。来源与地址映射留在外部 Parquet/manifest，不进入 MFM4。

默认训练条件：P 排除 M13；普通 U 需 M17 且排除 M14；U 的 P′ 训练需 M18 且排除 M14。M18 直接复制已完成的实际 source binding/first2/Common TRAIN/D5 排除结果，不由 loader 或 exporter 重新判断；保留的其他旧 P′ 原值不会自动扩张训练范围。最终角色及 Common 标记仍适用。M13/M14 按原实际 D5 GID/物理身份，不按新的 last 位置替换。

用户批准的 r73 σ–σ/π–π 块和复用 D4/独立 P′ typed cache 中的原 F64 聚合值及有效 mask，绑定同一原 K 有向端点首次出现顺序，单次 F32 写入 pair_labels 两列。schema.derived_r73_pair_targets 给出两个 selector；array27 列数同步增加。mixed/δ 不进入两列；raw r73 数组31–34完整保留。新库训练优先预聚合两列；历史 D3 缺这两列时只能从原 raw F32 K 聚合，明确其历史存储精度，不重导出或重扫旧库作为本次前置门。

每 split 顺序写完、关闭、compact 一次；新 owned scratch 与最终 compact 可在不同实际文件系统，关闭并消费后正常回收本轮 scratch，不删除旧文件。末尾唯一一次 1000 个实际 P/U source 样本检查在原 F64→单次 F32 流中累计误差，再对 compact 数值/整数/NaN/计数检查，包含两列新聚合值；不恢复已历史删除的 v3.0，不独立重读原源、不计算新 SHA。分发仍 rsync --sparse；成品实际大小决定节点，传输恢复不重做 producer QA。
实际normalization引用按原final_release_v1.produce.normalization条件契约：condition=Pprime使用独立Pprime统计，其余标签条件（包括D3）使用P_D。故本次UFF真实D3/atomicSASA引用最终PM7全TRAIN P_D的对应字段统计，不声称独立UFF拟合，也不混合PM7+UFF重拟合。schema/最终manifest分别明列两套实际引用；导出值始终raw，未执行归一化。

## 2026-11-06 最终数据共享存储修订

用户要求最终 LMDB 不再逐节点复制，以免重复占用存储。最终 D6 的 TRAIN/FULL 划分与 v3.1/MFM4 格式保持不变；每个 split 只有一份共享 compact LMDB，各模型节点只读同一路径。共享发布根为 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/export/D6_full_v31_20261105_v1/compact`，最终 `manifest.json` 的 `split_roots` 和 `schema.json` 是模型接入入口。当前 `gpu_nodes=[]`，不再添加节点目的地或执行节点分发。任务书中 D6 的逐节点分发要求由本次明确指令替代；最终导出及唯一生产端检查闭合后，在 STATUS.md 通知共享读取路径，即完成存储交付。
