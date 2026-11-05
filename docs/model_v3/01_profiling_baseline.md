# 阶段 1：6×512、A4、S 任务性能测量

日期：2026-10-25（Asia/Shanghai）。状态：阶段1验收通过。原生S三卡实测、
9份trace分析及4520378汇总均已闭合；主agent已核对数值并逐张查看三张PNG。
本报告仅支持性能瓶颈结论，不授予A/B等价性或架构选择验收。

## 问题与预注册

问题：距离偏置 MLP 是否主导现有 S 路径的时间和峰值显存？数据加载、
QKᵀ、softmax、AV、FFN、等变去噪头、其他预测头、损失、反向和 AdamW
分别占用多少时间？3090、4090、5090 上的填充与吞吐表现如何？

预注册：`3441b280bc34431bf8e7596465af28be073644b6`，
`docs/model_v3/DECISION_RULES.md`。代码实际提交号、源码逐文件 SHA 和
配置哈希另由每次测量记录；不能用报告中的预注册号代替实际运行代码版本。

## 基线的精确定义

- 主干 6 层、512 维、8 heads、ff_mult=2；shared-light；A4 等变噪声头
  半径 5 Å、32 RBF、hidden=64、0 层 message、chunk=8192。
- 原生 TRAIN 记录与三视图来自既有 S `training_inputs_v1`，逐条验证原
  LMDB payload SHA，原库只读。输入清单与冻结 S 引用的原始 SHA 必须匹配。
- 保留旧 S runner 实际使用的 `TiledDistanceMLP`：每块 65,536 对，每块
  non-reentrant checkpoint；主干层 checkpoint 开启，A4 头 chunk checkpoint
  开启。不是直接把未分块的 dense MLP 当作旧生产路径。
- fp32、TF32 关闭、未请求 fused AdamW。S loss 保持 A4 已声明的三个子任务，
  dynamic balancer 关闭。噪声 seed 明确包含 epoch，采样器 epoch=0。
- 采样上限为512基础结构、65,536原子、8,000,000 padded cost，桶宽16。
  配置可显式下调 padded cost，但这会成为新的测量条件，必须逐表列明。

## 工具与度量定义

原全20步同时记录torch.profiler的版本因CPU/输出限额失败，原失败保留。
已预先提交的v2协议执行2个warmup、20个测量更新，只在相对0/10/19三步
各自建立、导出并释放独立profiler；其余17步用完整step墙钟计算主要吞吐。
完整20步循环墙钟另存，包含trace分析/导出，不能拿它代替17步吞吐分母。
每步记录 W&B offline、完整有效标签计数、已消费逻辑
索引、记录 ID、loss、梯度范数、loader wait、计算耗时和实际 CUDA 内存峰值。
profile 之外的模型参数、模块名和 H0 接口不变。

`current/phychem_mfm/model/v3_profiling.py` 临时标注密集注意力的 QKV、QK、
距离计算、距离偏置 MLP、mask、softmax、AV、projection，以及 FFN、去噪头和
其他预测头。上下文退出后恢复原 forward；其输出、梯度及恢复行为有独立测试。

原子填充比例 = Σn / (B·max(n))；注意力原子对比例 = Σn² / (B·max(n)²)，
后者含对角线，与实际 dense attention 的容量一致。三视图同时扩展分子和原子，
不会改变这两个比例。报告同时给基础结构/秒、分子 ID 呈现/秒、native atom/秒
与展开视图 atom/秒，避免把多个构象误称为多个唯一分子。

Profiler 标注的 CPU/GPU 时间是 inclusive 子区域时间。前向子区域、checkpoint
重算以及完整 backward 区域存在嵌套，不能直接相加画成独占时间饼图。
operator 的 net allocation 也不等于其对全局峰值的因果贡献。整体峰值取
CUDA max_memory_allocated/reserved；保留原始 trace，以便复核分配发生时刻。
17步吞吐包含loader、W&B和资源观察开销，排除了独立trace的分析/导出；
这是一次短程、带管理开销的实测，不是长期生产吞吐。
旧外层dist_mlp区域未覆盖每tile在backward中的全部再重算。新增
`v3_profiler_attribution.py` 对tile方法、内部算子及去噪chunk另加标签，
从CUDA correlation和autograd sequence关联唯一kernel；无法确定时保留unknown。
独占GPU时间按每张卡的kernel区间并集分区，重叠的不同组件另列concurrent；
CPU各线程self墙钟、可重叠kernel时长之和单列，不能相加当作GPU独占时间。
内存分配点的live block观察不声称因果峰值分解。4520350定向31/31通过，
4520369实际9/9分析通过；旧smoke不补造缺失标签。原dense第一隐藏张量的
尺寸公式不用于本报告的实测结论；本次路径始终是tiled65536+checkpoint。

## 执行方法

由主 agent 先核验 Slurm、实际 GPU UUID/类型、CPU/主机内存、其他进程、quota
和输出预算。不得直接运行学校服务器或历史提交协调器。示例（在自有 allocation
内，由外层设置一张完整 UUID 为 CUDA_VISIBLE_DEVICES）：

```bash
python -u tools/model_v3/profile_s_baseline.py \
  --input native_s --expected-gpu 4090 \
  --shard-snapshot-sha256 PREJOB_ORIGINAL_SNAPSHOT_SHA256 \
  --steps 20 --warmup 2 --code-sha ACTUAL_CODE_COMMIT \
  --output /external/model_v3/stage1_4090_JOBID
```

原始`shard_snapshot_v1.json`按提交前固定的raw SHA绑定，原文件不修改；
既有v2 adapter仅对自己的独立副本投影节点本地st_dev，原rawSHA另行保留。
native测量必须通过supervisor设置`--private-scratch-root /tmp/mv3n_JOBID`
和`--private-storage-budget-bytes 2147483648`，由supervisor首次创建0700目录。
TMPDIR、CUDA、Inductor、Triton、Torch extensions和XDG缓存均显式指向
该任务私有根或另行明确绑定的compiler-only cache。现有cache字节、复用状态、
初始大小与0.5秒采样最大值分开记录；采样最大值不是精确峰值。持久输出与
私有存储各自遵守2GiB上限，不用扩大默认预算掩盖原始trace溢出。
子进程、loader和SDK实际闭合后，独立CPU调用`analyze_trace_v3.py`生成
trace原始SHA绑定的紧凑归因报告，避免与profiler内存叠加。

正式测量必须使用 fresh 外部目录。先执行 `--input synthetic --steps 2 --warmup 1`
可检验 GPU 路径和持久记录，但该结果不满足真实 S 基线验收。

原始产物为 configuration.json、steps.jsonl、profiler_operators.json、trace.json、
summary.json、run_status.json 和 W&B SDK 文件。大 trace、真实记录 ID 和原始
管理文件保留在仓库外；论文所需的小型汇总表和数字再提交到 GitHub。

## 原生S实测结果

实际code SHA：`dc22d3f3bb68ce6949bf40f38e677f74a35c407d`。
3090/4090/5090分别为4520365/366/367，Slurm全部COMPLETED/0:0，
ElapsedRaw分别217/173/143秒，均16CPU、ReqMem=64G。原始根为
`runs/model_v3_20261025/native_v2_{GPU}_{JOBID}`。4520369逐份分析9个trace，
并已核对三卡20步的ordinal、logical_indices和record_keys全部相同；汇总脚本
会再次核对输入receipt、科学配置、原始数据SHA及真实终态。

| GPU / Slurm | 17步基础结构/s | 分子ID呈现/s | native atom/s | 加载占比¹ | 20步allocated / reserved峰值(B) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 3090 / 4520365 | 89.599 | 49.354 | 5,452.631 | 0.1691% | 5,314,247,680 / 10,905,190,400 |
| 4090 / 4520366 | 115.851 | 63.814 | 7,050.190 | 0.1710% | 5,314,247,680 / 10,905,190,400 |
| 5090 / 4520367 | 163.961 | 90.315 | 9,978.000 | 0.2576% | 5,314,247,680 / 10,905,190,400 |

¹原summary的加载占比为Σloader wait/(Σloader wait+Σcompute)，不是总step墙钟
比例。完整17步墙钟分别73.002928、56.460607、39.893567秒；端到端加载比例
另由紧凑汇总根据原始step记录给出。分子ID呈现是逐批distinct molecule ID之和，
不是跨整个运行去重的分子人口，基础结构则是实际消费的record/构象。
20步加权原子与原子对有效比例三卡均85.7607%与74.8664%；17步同口径比例
另单列在汇总产物，避免把不同窗口混用。

| GPU | 节点 | Torch / CUDA | driver | Torch观测可用总显存(B) |
| --- | --- | --- | --- | ---: |
| 3090 | compute-0-0 | 2.10.0+cu126 / 12.6 | 530.30.02 | 25,438,126,080 |
| 4090 | compute-0-20 | 2.10.0+cu126 / 12.6 | 560.35.05 | 50,896,044,032 |
| 5090 | compute-0-21 | 2.10.0+cu128 / 12.8 | 590.44.01 | 33,671,348,224 |

4090的容量按实际记录使用，不能按常见24GB预设。前两卡用chemprop逻辑Python，
5090用已验证的独立stage43 venv。环境/driver/容量不同且每型仅1次运行，这些
数值不能解释为受控的GPU架构提速因果效应，也不是A类候选的提速倍数。

## GPU时间与显存假设

以下来自独立唯一kernel区间并集，单位ms；重算与梯度backward分开。它们仅覆盖
相对0/10/19三个代表更新，不外推成20步完整组件普查。unknown保留，不分摊。

| GPU | 相对步 | 全kernel busy并集 | dist forward | dist replay | dist backward | unknown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3090 | 0 | 3671.431 | 569.635 | 1015.258 | 640.309 | 195.413 |
| 3090 | 10 | 2627.939 | 582.154 | 1036.189 | 674.886 | 11.750 |
| 3090 | 19 | 1470.051 | 287.957 | 512.346 | 334.157 | 13.861 |
| 4090 | 0 | 2830.951 | 489.982 | 867.608 | 548.741 | 145.739 |
| 4090 | 10 | 2155.826 | 500.502 | 886.422 | 578.393 | 8.383 |
| 4090 | 19 | 1162.769 | 247.805 | 438.120 | 285.762 | 10.257 |
| 5090 | 0 | 1777.618 | 295.662 | 522.260 | 319.249 | 95.890 |
| 5090 | 10 | 1308.160 | 302.361 | 534.920 | 337.274 | 5.341 |
| 5090 | 19 | 715.296 | 149.563 | 263.952 | 166.752 | 6.476 |

据这9个已分析样本，dist_mlp的forward+replay+backward是最大的已归因GPU
组件，并占各样本kernel busy并集的一半以上，支持其在当前tiled/checkpoint
训练路径中主导GPU计算时间的假设。该判断不是由inclusive标注时间相加得来。
QK、softmax、AV、FFN、去噪头、其他头、loss和optimizer的完整独占行保留在
紧凑JSON与组件图。memcpy/memset事件不进入kernel并集，另保留数量诊断。

CPU self是各线程self墙钟总和，含等待，不是CPU利用率，更不能加进GPU并集。
仅以相对0步的dist_mlp为例：

| GPU | CPU self forward(ms) | replay(ms) | backward(ms) |
| --- | ---: | ---: | ---: |
| 3090 | 418.912 | 726.796 | 1256.343 |
| 4090 | 367.250 | 501.924 | 1038.812 |
| 5090 | 203.550 | 376.938 | 558.065 |

显存假设不能作相同结论。三个采样trace的allocator峰值三卡一致，分别为
4,883,229,696、1,816,214,528、1,615,613,440B；最高采样峰值仍低于完整20步
allocated峰值5,314,247,680B。最高采样峰值的observed-live-site包含
forward_other=1,427,226,112B、denoising_head=994,554,368B、FFN=990,904,320B，
unknown=4,525,056B，另有未追踪/未对齐残差220,089,344B。该时刻没有dist_mlp
live-site条目；另两份采样峰值则分别观察到199,229,440与98,736,128B的dist_mlp
live-site。它们是分配点库存观察，不能解释为各组件对峰值的因果贡献。
MLP的大量累计分配/churn、原dense隐藏维度算式、单个allocation事件发生位置
都不能证明它是当前显存主因；当前显存主因假设保持未证实。需要独立匹配消融
和容量实验才能判断，不能据本结果直接修改架构或checkpoint默认。

## 旧失败、资源与产物

| 原任务 | 实际Slurm状态 | ElapsedRaw(s) | 首个已记录原因 |
| --- | --- | ---: | --- |
| 4520352 / 3090 | FAILED/1:0 | 1114 | own RSS超过56GiB保护，监督child exit=-9 |
| 4520353 / 4090 | FAILED/1:0 | 1071 | trace消耗预留finalization空间，child exit=1 |
| 4520354 / 5090 | FAILED/1:0 | 1552 | 同一trace预算错误，child exit=1 |

后两项run_status明确failure=`Trace consumed reserved finalization space`、
cleanup_errors=[]、输入句柄关闭；352不补造未写出的正常child终态。三项失败
不是数值不稳定，费用和partial均保留。v2通过减少同时驻留的profiler范围解决，
没有提高56GiB RSS、2GiB持久输出或2GiB私有存储限额。

实际资源/成本来源为`runs/model_v3_20261025/job_ledger_through_369_v1.json`
及同名原始.psv。新三项CPU分配秒3472/2768/2288，旧三项17824/17136/24832；
本报告的六任务子集单独汇总，不能使用全任务97824CPU秒替代阶段1成本。
AllocTRES没有GPU GRES；单GPU任务的allocation墙钟不是GPU利用率，也不声称
未登记GRES的卡被Slurm预约。其他CPU回归、旧synthetic、分析369等费用仍在
完整30个已登记父任务账本中，本六任务子集没有覆盖整个阶段的全部成本。

`tools/model_v3/summarize_baseline_profiles.py`只读取固定三summary、9 attribution、
369分析receipt和ledger，以及对应配置/step/监督metadata。它生成外部
`baseline_summary.json`、一行/run的`baseline_runs.csv`和3张PNG；CSV满足主树
新checker的required字段、metric__数值列及128KiB限额。JSON/PNG每文件≤2MiB，
总产物≤16MiB，Matplotlib cache也限于本次外部目录并计量。原始trace不搬入Git。
脚本只沿用369已实际计算的raw trace SHA并复核原文件size，明确不重复哈希巨型
trace。主agent统一Slurm运行、检查数值/CSV和图像后，再复制小产物到results目录。

## 决策与限制

实际 CPU 证据：4520331 的标注/输出/梯度/state-key/异常恢复3项通过，
合成 S fixture 因测试调用遗漏 compute_phase1_loss 必需的 schedule/exposure
参数而失败；原失败与源码快照保留。修正后仅补这1项，4520333 已实际
COMPLETED、ExitCode=0:0，该项通过；没有为修正 fixture 重复另3项。
4520333 同时通过8项 A/B 候选组件测试，共9项。它们不证明真实训练性能。

4520339完整`current/tests`实际2040项全部PASS、无skip，Slurm
COMPLETED/0:0/97s；checker检查1727文件通过。这是实现回归，不是阶段1验收。
4090首轮4520340实际FAILED/1:0/14s、0次optimizer更新：Torch动态模块的
相对伪`__file__='_classes.py'`被错误归入仓库。原错误、源码和费用保留。
修复只收录真实绝对仓库普通.py，并对显式必需源继续严格拒绝缺失；4520342
两项定向回归实际PASS，前后源码SHA一致；修复提交为
`14b98d03932b53b2d4f132afb69c4e652b747888`。

该提交的4090 synthetic smoke4520343实际COMPLETED/0:0/228s，
2测量步、1warmup、每批3基础结构×3视图；profile耗时1.091558s，
CUDA allocated峰值335,738,880B、reserved峰值356,515,840B，trace后总输出
16,893,908B。run状态PROFILE_COMPLETED、failure=null、cleanup_errors=[]，
输入句柄关闭；外层监督COMPLETED、无retirement，无foreign操作。
W&B run `8rdupcyh`为offline。冷启动阶段观测到页I/O等待，原因未定位，
不能据总墙钟断言模型计算慢。这是合成小样本路径验证，不是原生S吞吐或容量。

当前9个代表样本支持dist_mlp主导GPU计算时间；显存因果主因仍未证实，不选择
架构或采用A候选。三GPU实测及369分析已闭合，4520378实际COMPLETED/0:0、
13秒，生成脚本执行版本为044a29f3c2a415f8b79a9f18c3b3b152e86192ee。
主agent复核三卡输入一致、17/20步分母、环境差异、失败费用及分配点库存口径，
并逐张查看三张PNG，图像可读。小型原始汇总按字节复制到本报告旁的results；
summary内部READY_FOR_ROOT_REVIEW字段作为生成时原始状态保留，当前验收由本报告记录。
阶段1可供阶段2和SA-4确定实现优先级；后续数值和科学选择仍需各自验收。

- [逐运行结果表](results/baseline_runs.csv)
- [原始紧凑汇总](results/baseline_summary.json)
- [GPU组件时间](results/baseline_gpu_components.png)
- [吞吐与加载等待](results/baseline_throughput.png)
- [采样allocator库存观察](results/baseline_allocator_observation.png)

外部监督入口为 `tools/model_v3/run_supervised.py`，只启动一个显式命令，
不提交 Slurm；按实际 child argv、UID、boot/start_ticks、PGID/SID 和 Slurm
cgroup 绑定进程，逐 PID 再核验后只收尾本次子树。运行期 foreign GPU
进程记录风险，不发信号。4520336中资源/身份helper10项实际全部PASS，
父作业失败属于其他组件，未改写其终态。4520337真实W&B0.28.1 offline布局
探针COMPLETED/0:0/10s，四类已允许SDK链接匹配、两条commit history原生读回
一致，run `5fpnfle0`；没有声称在线同步。新增native pin/归因/私有存储接线已由
4520350的31项定向回归和本次v2原生运行实际覆盖；W&B仍为持久offline。
