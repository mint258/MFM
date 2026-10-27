# 模型 v3 实际进度 v23（2026-10-28）

本报告延续 v20/v21 的整份阶段 0–7 目标。新增闭合为四份 R2 日志的完整离线核验及精确选择同步、被动投影诊断捕获；C4 仍未通过，最终 D 数据、真实架构/配方矩阵和交接尚未完成。未启动学校正式预训练，未冻结最终模型、recipe 或 B*。


## 本次实际闭合与边界

| 项目 | 实际结果 | 尚不能据此声明 |
| --- | --- | --- |
| manual / auto R2 | GPU 4523976 与 4524551 的原 20 批数值门及 500 更新已闭合；auto C0/2274 秒，forward、gradient、loss-relative 最大差均为 0 | R1/ABBA、A5、三类 GPU 完整速度覆盖，或跨 seed/UUID/workload 容量资格 |
| 四份原生 SDK | CPU 4524559 C0/101 秒；原生 config 全字段、两个 paired_role、各 500 行 step1–500、自动 last-value summary 完整 typed 比较，前后原字节绑定闭合 | GPU 的 20 批门没有伪装成 SDK history；该证书不套用 Native 九任务面板 |
| 精确选择同步 | 4524561 C0/34 秒与 4524562 C0/19 秒，各精确复制并同步两份原件；远端 finished/500 行/1–500 已读回 | 远端每个 metric 的值没有另行独立重比；不自动宣称集中 CSV/HTML 归档已完成 |
| passive trace | GPU 4524563 C0/63 秒；完整 48 case、192 次 FP32 forward、1728 stage/512 geometry/2304 projection-port 观察，2496 终端控制逐位等于 4550 | 无新模型、数学修改、FP64 encoder 或局部重放；没有全模型原因排序或 API 改变结论 |

passive 中物理结果仍为 **12 PASS / 36 FAIL**，与 projection 4550 一致；原正式 C4 的 **21 PASS / 27 FAIL** 单独保留，均无 adoption，容差仍为原 abs=1e-5、rtol=0。保存的层观测已由CPU4564完整分析并Root闭合，见下节；捕获成功本身不代表科学通过。

四个实际在线 run 均在 mint_leaf258/mfm_model_v3_development；role 由 CPU 读取原生配置确定：

| GPU 来源 | role | run | 独立核验 / 实际同步 |
| --- | --- | --- | --- |
| manual 4523976 | reference | [z4ts32w5](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/z4ts32w5) | 4559 / 4561 |
| manual 4523976 | candidate | [dr7zahoj](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/dr7zahoj) | 4559 / 4561 |
| auto 4524551 | reference | [5thxuhw5](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/5thxuhw5) | 4559 / 4562 |
| auto 4524551 | candidate | [zotxsoay](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/zotxsoay) | 4559 / 4562 |

已知在线总数 **74**，沿 Root 已闭合的原 70 加本次四个 run 记账，并非本稿重新 API 全量盘点。prepare v1 的 nested-descriptor KeyError 在创建 plan 前失败；旧源/失败回执保留，v2 窄修接线后实际核验及同步成功，没有改写旧证书归属。

## 保存层观测的实际离线分析

CPU4564实际C0/4秒/16CPU，完整48例和192份保存数组；1296项层比较、384项几何比较、144项坐标比较，共9120条人口统计记录、2865个汇总组。403653679字节输入在512MiB上限内，原数组及全部输入前后哈希匹配。没有新encoder/head/model调用，CUDA未初始化。

| 变换 | 坐标F32转换残差最大值（Å） | packed H0差异最大值（特征分量） |
| --- | ---: | ---: |
| general_rotation | 2.335300E-07 | 1.765788E-06 |
| translation_only | 2.384186E-07 | 1.668930E-06 |
| other_rotation_and_translation | 2.372159E-07 | 1.728535E-06 |

表中覆盖全部原案例和物理视图行。H0差异的尺度不能替代终端物理门槛，也未据此确定终端失败因果；几何D=B+C+A按同一分量核对，Å与Å²分开统计。正式21/27和候选12/36保持不变。

## 原配置、代码、数据与 seed

两项 R2 均为 seed 0、6层/512，同一 Native S 数据人口与采样合同。每份原配置的 /model、/data_version、/source_sha256 保留完整来源，不把事后摘要充当原配置；精确 rawrefs 见同目录 pretraining_preparation_compact_evidence_20261028_v3.json。

| 原训练来源 | 原配置（PROJECT 下） | 实际 code / 原 public 方法 |
| --- | --- | --- |
| manual 4523976 | runs/model_v3_20261026/performance_manual_R2_v1/child/configuration.json | 本地执行代码 9e16d4c5a15c558051499d3dc0c55c9bd3787734 / [8147f44b](https://github.com/mint258/MFM/commit/8147f44baa1ea1ecc3822af7affd0a95401ed248) |
| auto 4524551 | runs/model_v3_20261026/performance_auto_R2_v1/child/configuration.json | 同上 |

原数据 manifest 为 /share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/training_inputs_v1/manifest.json，raw SHA 2f69b672350744369b08c672b62e3d276487714abc97b766a12140ec5af59997；view SHA 138daeaccd91a627b7e80ea5f1b032721438331f28d0244f764c4e10b5f1bfaf，sampler-contract SHA ecb67948413fe6b1a507ecec8e95bc864fa439eb7be09e1f1b174e105d0da50e。这是既有 Native S 来源，不能赋予 D5/D6 或最终数据冻结权威。原配置 raw SHA：manual e499f52deae6eeb0799447d78454bfdd14a3ae600b8de5f56a4f0f3996cb2b9a；auto 9e50d047d13370d3b235465d9731f24807d1ddf054cb906d48208f07a2a6d783。

Native S10000 描述性开发面板保留 GPU 4476 C0/518 秒、seed0/fp32、10000 更新/4076032 consumed-base records：producer 3d9b1cc0c580dacc9398a5570b0c2fff3e257618，evaluator 17f975bb094c9c3ec010d7f8134c5700adcc85e4，对应 public 60aa359443ef6a79aabc08144d2af4eec7ec24c5。原 request/spec 与 CP 六 bindings 可沿 compact evidence 的 Root closure 追溯。冻结 TRAIN 内层9任务×2读出、1000 bootstrap、matched random512不变；SoM3条及 Expansion48条原来源几何不可用记录按原政策双方同样排除，QM9为0，不能称覆盖全部最初选择记录。

其日志 CPU4552 完整核验170295 native packets/56738 history行；overlay4555实际C0后，mint_leaf258/phychem-model-v3/vcxcfx54 的 finished/56738行/step0–56737已读回。原4553同步工程失败保留；该成功不等于远端逐metric重比、D5验收或seed SD，旧B3也不能当Native同条件学习曲线锚点。已有旧S B3完整面板不重复评估。

## 原指南完成矩阵与剩余工作

| 原阶段/范围 | 已有证据与本次更新 | 尚未完成 |
| --- | --- | --- |
| 0 代码审阅 | 6层512/H0及兼容实现；整合训练链121模块2905 PASS、3项原可选SKIP | 后续新组合仍须完整源绑定回归；不扩大工程证据为科学验收 |
| 1 性能测量 | 已有实际短程、容量与资源观察 | GPU型号/批大小/工作负载完整覆盖及真实训练对应性能；paired不作standalone速度 |
| 2 等价提速与bf16 | manual/auto R2的20+500及真实消费、四份日志已闭合 | R1/ABBA、A5及三类卡完整覆盖；代理S四次2万步（fp32/bf16各两个种子）的曲线波动范围及去噪RMSE差异不超过2%验收；4090的4558与原1338在v37时仍PENDING |
| 3 标签、预测头与损失 | 工程实现/恢复链及passive逐位控制 | 正式C4仍21/27；真实D3全字段1000分子过拟合、各卡SDP与真实标签验收 |
| 4 开发评估 | 旧S B3与Native S10000各自真实9×2；Native SDK/选择同步闭合 | 后续端点/模型各自评估；单seed非seed SD，fallback不作D5选择 |
| 5 架构与预测头对比 | 源码、预注册和失败诊断保留 | 真实D5的C1六次/C3四次、预测头九次/池化一次、约六次重复及seed SD、600万样本预算平台 |
| 6 训练配方 | 配置、决策器及proxy/full/恢复工程入口接通 | 19项真实LR/B/WSD/SDP搜索、完整有效TRAIN preclip p99、D6 S/P至64M倍增平台/1SD/B*较大值及超过2倍报告 |
| 7 冻结与交接 | 合成6×512真实CLI更新→安全CP→新进程恢复→H0/随机/ACK链 | 真实120k/k2/1M E2E、全数据/科学验收、用户确认最终recipe/B*、最终tag/HANDOFF/PR与整合验收 |

数据接口独立保留：D1当前权威仍draft3，draft5为条件审阅，未joint-freeze。数据线持续推进不等于最终D1–D7已齐，模型工程适配不能替代数据线最终交付。不得因日志或报告发布缩减原目标。

## 公开来源与点时成本

方法v22的 model-v3 公开提交 40b2d93e1733c0833972ce452b90117755396493，本地 bb18bbc7b480449c085b9e49b76fe6cf0f18f25c，精确tree 15e91aee6084c3d1f4c5f31a91058873f634ddc5；checker4524560实际C0，API branch/tree readback闭合。这是开发方法发布，不是最终main合并、模型采用或最终freeze。

v37采集于 **2026-10-27T21:05:51.024462+00:00**：**533**个实际父作业，分配CPU **1,639,936核秒**，GPU节点作业分配时间 **79,969秒**。4559–4564均已计入；模型活动条目仅1338/4558，均PENDING。这是点时分配记账，不是利用率、独占性能、金额或整份任务最终成本；旧失败与重试完整保留。

精确path/bytes/SHA、闭合范围与原配置/代码/数据/seed投影见compact evidence。本稿不复制SDK、训练成员ID、数组或权重。后续仍须FP32修复、R1/ABBA/4090工作，以及权威数据就绪后的原指南全部真实矩阵；已有日志成功不能替代未完成项。
