# B3 最终实际前二 P′ 交付

最终 Common TRAIN/VAL 范围为 1,200,832 个 MID、2,396,675 条实际固定随机前二记录；复用既有闭合几何标签 2,367,432 条，只新增完成 29,243 条。不足两个真实几何的原因保留在 scope 原状态表，不复制、不补齐、不另生成 N1，不计算第三及以后构象。

闭合 Native parent 为 4526126（COMPLETED，0:0，elapsed 05:59:13）。保持原十二任务、每调用 900 秒和 seed 20261025。新增记录中 28,796 条十二项均成功，447 条实际任务失败按原标签与掩码保留，未解决记录 0；不外推复用子集的成功率。

历史初批 80,728 个分子、161,456 条记录的交付保留：原 ready 之后闭合的 80,740 个 TRAIN/VAL 成功补齐分子，扣除 12 个已 ready，得到 80,728 个初批缺失 MID。原缺失 MID 引用、原始原因、161,044 条全成功和 412 条科学任务失败均在最终配置 historical_initial_fill 中保留；这批原文件和更早 ready 原标签均未重算或删除。

- [最终配置](../../configs/data_v1/Pprime_final_first2_v1_DELIVERY.json)：完整计数、path/bytes、逐 family 元数据及状态表引用。
- [历史初批配置](../../configs/data_v1/Pprime_initial_fill_v1_DELIVERY.json)：原缺失原因与原 MID 表。
- 最终 scope：`/lfshome/zixiao/data_v1_20261025/window2_final_pprime_scope_20261106_v3/manifest.json`。
- 新增 raw root：`/lfshome/zixiao/data_v1_20261025/window2_final_pprime_labels_20261105_v1`；初批 raw root：`/lfshome/zixiao/data_v1_20261025/window2_pprime_fill_20261105_v1`。

本交付仅闭合 B3 最终实际前二计算；D4 独立统计、D6 和 Model ACK 由各自交付声明。统计直接复用原 producer 元数据，无额外 SHA、数值读回、独立 QA 或逐作业验收收据。
