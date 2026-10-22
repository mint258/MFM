# 服务器代码同步：2026-10-23

本次将 `zixiao@202.38.247.57` 上已完成工作的代码同步到 `mint258/MFM`。没有启动训练、重算标签、改写原始数据或删除数据。

## 当前源码

- `current/phychem_mfm` 合入 S 去噪修复的 **Source v3**：等变去噪头、输出结构、共享模型、去噪指标、完整语料加载、目标函数、损失及相应测试。
- `workflows/s_denoise` 保存 Source v3 实际配套运行代码与配置。
- `workflows/s_denoise_repair` 补充服务器上的分析、测试、配置及正式工作流脚本。历史提交、恢复和清理脚本仅用于追溯，不能批量执行。
- `workflows/wp5/scripts` 补齐 WP5 最终验收、失败分析、盘点与交付脚本；正式 runner 的科学参数没有在本次同步中修改。

本次 Source v3 绑定来源为服务器 `runs/s_denoise_repair_20261016/configs/D3_source_binding_v4.json`，其中 99 个源码文件的 SHA 均在复制前核对。Source v4 是未采用的缓存候选版本，不作为当前科学版本。

## 历史与当前来源清单

保留原 `docs/SOURCE_MANIFEST.json`，不覆盖既有服务器导出的历史 SHA。Source v3 的清单另存为 `docs/source_revisions/s_denoise_patch_v3_SOURCE_MANIFEST.json`。本次新增的逐文件来源与 SHA 见同目录的 `server_sync_20261023_manifest.json`。默认仓库检查应通过；`--verify-export` 用来核对原始导出，不能把旧清单中的字节当作已合入修复后的当前版本。

## 已完成工作的实际状态

WP5 已完成：1,220,466 个分子、11,231,854 条记录、12 类计算的显式状态槽；最终交付包含 family parquet 和按失败/审计策略保留的原始输出。pilot 的差异及历史例外保留在验收材料中，不能把“交付完成”理解为与旧 pilot 的所有数值逐位相同。

S 去噪修复 Source v3 已执行代码测试和科学诊断，但最终未满足指南的全部科学闸门，已按要求 **GUIDE_STOP**。同步代码不意味着授权重启旧工作流或进入正式预训练。

## P/D 标签整合仍待实施

最新训练实现仍以含 Kappa1/2/3 的 23 维旧图描述符为 D 头接口，P 损失仍处理能量和电荷。WP5 D20/D3 和其余 P 字段尚未全部接入训练加载、预测头、损失及 TRAIN-only 归一化。S 去噪补丁不改变这一接口现状。

WP5/S′ 数据与原 LMDB、权重、缓存、数据库、原始计算输出继续保存在 Git 之外。本次不创建新的训练格式，也不改变数据划分、原子顺序或缺失掩码。

两份已有语法错误且已被替代的历史草稿 wp5_reproduction50_v1.py / v2.py 延续原 docs/VALIDATION.md 的排除策略；服务器原件保留。本次复制时的仓库检查再次检出这两份草稿，未将其作为可执行源码上传。
