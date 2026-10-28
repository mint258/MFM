# 2026-10-29 CPU自动内存/A5-v2/残差FP32/Native续接

四项候选源码的完整 CPU 回归均通过；A5 在修订后的逐元素梯度门下失败，残差 FP32 的完整 48 案例仍未全部通过。Native S 已恢复原检查点续接。本记录是完整 Stage0–7 工作中的阶段报告，观察时刻与原始来源见文末记录。

## 1. 问题

本阶段处理四件事：按用户授权完成 CPU 自动内存请求后的完整回归；以新梯度规则复核 A5 logical-batch 路径；检验统一六层 FP32 残差累加候选；在保留安全检查点和旧失败记录的前提下恢复 Native S 续接。CPU 工程通过、局部前向相近或通过案例数增加，都不能替代相应科学验收。

## 2. 预注册与公开来源

| 项目 | 公开/预登记来源 | 本地来源 |
|---|---|---|
| A 梯度规则 v2 | [`4f6ba16`](https://github.com/mint258/MFM/commit/4f6ba16973ea4a30472c7fb33d3aadec974a4462)，先于本次 A5 复核公开 | 用户批准的新规则，A 保持原 bias |
| A5 / A-v2 候选 | [`2b4a4df`](https://github.com/mint258/MFM/commit/2b4a4df8636e5d65915d535472ba01084ea72dab) | `7ffe` |
| 残差 FP32 候选 | [`380c828`](https://github.com/mint258/MFM/commit/380c828db0ac4a37e45b7cc5077de9b56e37a67d) | `1a81` |
| C-only 距离偏置候选 | [`481943f`](https://github.com/mint258/MFM/commit/481943ff1da79f096d61f4b04914ddf45a56a4a6) | `c563` |
| tensor 候选 | [`49d610b`](https://github.com/mint258/MFM/commit/49d610bba1cadef7fd80fab70435cd944cce7722) | `98ec` |
| 本次归档前 reporting | public `1559`，tree `c166` | local `617d` |
| D1 候选 | [`651a874`](https://github.com/mint258/MFM/commit/651a87431c4bc02b47edbf495043c9c217e98c23) | 仍为 joint 候选，未冻结 |

新规则对全部梯度参数逐元素要求 `abs(candidate-reference) <= 1e-8 + 1e-4*abs(reference)`。六个解析零参数还必须满足候选和参考各自梯度范数均 `<=1e-8`。A 路径不删除 bias；冗余距离投影 bias 的删除仅属于独立 C-only 候选，不能借此使 A-v2 过关。

## 3. 源码、数据与配置

CPU 四项完整回归使用实际对应源码，均由 Root 闭合。用户授权本轮 CPU 提交不设置 SBATCH 内存大小；软件工作内存预算为 32GiB、RSS 上限 24GiB，16CPU 单父运行四个 pytest 子进程。站点实际读回 `ReqMem=375000M`，`AllocTRES` 仅有 CPU/节点项，不能声称 Slurm 为每项获配了 32GiB。旧 4524660、4524626 仍保留原 16GiB 请求，不追溯改写。

A5 作业 4524704 使用源码 `7ffe` / 预登记 [`2b4a4df`](https://github.com/mint258/MFM/commit/2b4a4df8636e5d65915d535472ba01084ea72dab)，Native S、seed0、P8M、workers8，manual a00 加 logical chunks（桶 16/32 graphs、P1M）。资源为 16CPU、64GiB、RSS56GiB、6900s 内层限期和 2h Slurm；没有改梯度规则或模型以迁就结果。

残差作业 4524701 保留原 1492 参数身份、完整 48 案例、192 次 FP32 编码器前向、13 字段×3 变换、52 终端数组以及绝对 `1e-5` / `rtol=0`。新残差路径统一覆盖六层，未使用 FP64 编码器或混合精度代替正式 FP32 门。

Native 续接仍为原科学核心 `3d9`、原 UUID `22e` 和 32GiB GPU 作业配置；数据、科学配置、seed/update 身份与安全 CP17000 不变。CPU 自动内存授权没有放宽其既有 GPU 资源、UUID/锁或存储保护。

## 4. 结果表

### CPU 完整回归

| 实际父作业 | 项目 | 模块 | collected | PASS | 原可选 skip | 失败/错误 |
|---|---|---:|---:|---:|---:|---:|
| 4524695 | A-v2 | 115 | 2676 | 2673 | 3 | 0 / 0 |
| 4524696 | residual FP32 | 118 | 2954 | 2951 | 3 | 0 / 0 |
| 4524697 | C-only bias-free | 118 | 2949 | 2946 | 3 | 0 / 0 |
| 4524698 | tensor | 118 | 2941 | 2938 | 3 | 0 / 0 |

四项均已 Root 实际闭合。三项既有可选 skip 如实保留，不授予 CUDA、真实数据或科学阶段资格。

### A5-v2 完整 20 批次数值门

4524704 实际 `FAILED 1`，耗时 133s。20×8 条前向对照全部通过，最大相对误差为 `1.9975306379930165e-6`。但前向通过未带来梯度通过：

| 梯度记录类别 | 实际结果 |
|---|---|
| 总范围 | 329 参数×20 批次 |
| 双方 disabled | 4240 条，单独分类，不伪称解析零梯度 |
| 六个解析零参数 | 120 条全通过；最大范数 `8.722549703540776e-10` |
| 其余参数×批次逐元素检查 | 1779 条失败 |
| 最大阈值比值 / 最大绝对差 | `373.0778671103279` / `2.2821128368377686e-5` |

因此轨迹阶段为 0，未运行 500 步。原 4524601 的 v1 失败保留。首次 metadata closer 因 1-based 索引假设拒绝读取，原记录保留；独立后验 0-based reader（源短引用 `d6b11…`）闭合了已有结果（4299B，短 SHA `e2d057…`），没有更改规则/模型，也没有新 GPU 重跑。

### 残差 FP32 完整 48 案例

4524701 全部采集完成，结果为 **22 PASS / 26 FAIL / 0 error / 0 skip**，未通过原物理门。实际计数：192 FP32、0 FP64 编码器前向；1152 residual helper 调用；QKV、FFN 各 2304；69120 K64 leaves；512 geometry 调用。

Root 负结果闭合为 34721B（短 SHA `4b6aa…`），资源、进程和私有空间均闭合。额外 2GiB hold 已释放，原产物和注册 row 保留。旧 geometry 为 15/33、FFN 为 14/34，当前只作案例总数对照；尚不能称为逐字段或逐案例全面改善。

### Native 续接与成本点时账

Native v7 保留三次 pre-SB 兼容修复历史：缺 `durable_root`、历史 panel principal 变体、纯文本 log 被误作 JSON。4524705 CPU 的 30 项检查通过后才 adoption；GPU 4524706 已由实际 sacct 读回 `COMPLETED 0:0 / 2551s`。既有 coordinator 记录 `OUTER_C0_SEGMENT_CLOSED_SDK_PENDING`；新检查点及完整闭合正在独立核对。此前 history `laststep=17556` 仅是运行时观察，不能直接升级为安全检查点。四成员中 **0/4 达到 20k**。

成本 ledger52 已实际捕获成功：587 个父作业 = 420 CPU + 100 GPU + 67 other；累计 1,731,632 CPU 秒、84,289 GPU 节点作业秒。这是点时分配成本账，不是 GPU 利用率、收费金额或最终全任务总成本。

## 5. 决定

- A5-v2：梯度门失败，停止于 20 批次数值门；不进入轨迹/500 步，不采用。
- 残差 FP32：完整 48 案例仍失败，不采用、不升级为模型冻结候选。
- 四项 CPU 回归：作为各自源码工程闭合证据保留，不能替代 C/Tensor/FP32 物理或真实数据验收。
- Native：仅按原科学配置继续既有续接，保留原安全检查点和全部失败历史；只按已核验的段闭合推进，浮动 history 不当作安全检查点或 20k 完成证据。
- 九项旧 A-PASS 正准备按 v2 复核，首先处理原 4523976 A00 manual 的当前同源 profile；未复核者不升级为 v2 PASS。

## 6. 限制与未交付项

两条新 SDK 记录的 CPU 审计 4524708 和同步 4524709 已实际 C0，分别为 2s、21s；独立在线读回和完整闭合仍在核对。旧 87 条在线记录不为这两条提供替代闭合，不能提前宣称新两条已完成独立验收。

本阶段未证明残差处理的逐字段单调改善，也未建立全模型误差因果排序或普遍 FP32 精度下限。通过计数、最大局部误差及工程测试不能替换原参数、全场景、物理单位和绝对阈值要求。

D1 仍是 joint 候选；模型侧真实 D3/D4/D5/D6 联合验收仍未完成，最终配方及共同冻结尚未形成。完整 405 行 Stage0–7 目标保持，未缩减范围；没有开始正式预训练、没有运行 final test、没有发布 v3 tag。本报告也不是最终 HANDOFF 或配方冻结声明。

## 原始记录与复现入口

- 原指南：405 行，26121 B，SHA256 `e618165501d22556c4c421d93f1c01928fab3f50202ce6d0fec3249c79921239`。固定主干仍为 6 层、512 维，H0 API/维度保持。
- 原 Native S manifest：`2f69b672350744369b08c672b62e3d276487714abc97b766a12140ec5af59997`；原 shard snapshot：`d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f`。未读取下游最终测试标签。
- [四项 CPU 汇总表](results/source_CPU_20261029.csv)、[本轮实验表](results/experiment_snapshots_20261029.csv)、[残差完整 48 案例明细](results/residual_FP32_4701_cases.json)和[整项实验汇总](results/residual_FP32_4701_cases.csv)。表中运行态与成本均为保存时刻的观察，不升级为最终阶段验收。CSV 保持每个实际运行一行；CPU `config_sha256` 为冻结 request_spec 的原始 SHA256，残差为完整 48 案例执行请求的原始 SHA256，A5 为原生 configuration 中的配置身份。CPU 详细来源见[元数据表](results/source_CPU_20261029.json)。
- [九组旧 PASS 的完整复核计划](A_ACCEPTANCE_V2_OLD_PASS_RECHECK_PLAN_20261029.md)，及[机器读取计划](A_ACCEPTANCE_V2_OLD_PASS_RECHECK_PLAN_20261029.json)。旧结果保留原 v1 身份，新 v2 结果逐项另记。
- [A00 manual 新运行方法](pre_registered_methods/performance_manual_R2_Av2_v1/METHODS_README.md)。先形成当前源码的真实完整观测，再交给既有 closed-profile 消费器验证；auto 条件不使用旧源码 profile 冒充。
- [Native v7 操作修复源码](pre_registered_methods/native_S_long_operational_v7/README.md)、[A5 后验元数据读取适配](posthoc_methods/close_A5_R2_posthoc_v2.py)、[CPU 自动内存成本读取器](posthoc_methods/cpu_receipt_registry_v15_auto.py)。后验读取适配不改实验前的数值门。
- [SDK v3 资源适配源码](posthoc_methods/performance_A5_failed_SDK_v3/README.md)。4707 因旧 SDK 分配函数仍硬检查 16GiB 而在解码前失败；旧件保留。新独立适配记录实际默认内存环境，不修改 decoder 或模型规则。

| 原始闭合/快照（服务器 `runs/`） | bytes | SHA256 |
|---|---:|---|
| `model_v3_20261026/performance_A5_R2_v2/control/Root_closure_actual_v2.json` | 4299 | `e2d057781f45c725f67d265c459dca6139c9c9ade89adff95a236e160596acc7` |
| `model_v3_20261026/residual_fp32_GPU4701_Root_negative_closure_actual_v1.json` | 34721 | `4b6aa314eab659271a422ab0faa67261a3ad1042f46a5bb82b68793d3826bb90` |
| `model_v3_20261025/job_ledger_model_v3_active_v52.json` | 721307 | `9bba488d535a5dc55f7175a9851e53734a17df0e84eebe78bf798df8c01c7c75` |
| `model_v3_20261026/native_S_B20k_v3/control/OPERATIONAL_ADOPTION_v7.json` | 19673 | `ef9f3dd1a349d8a6c6d96a886f9eeb2adf6c5952c78a39d77f7921e445a5c704` |
| `model_v3_20261026/native_S_B20k_v3/control/attempts/slot_019.submitted.json` | 32805 | `0968c673838056bc0950c54a6fa27728ae8188cc3edf475d8723d4551fdc9775` |

