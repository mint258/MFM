# B 类四成员执行链：实现准备与验收边界

状态：473实际29项precision/trainer/performance检查全部通过；488/489/490/491
分支整树回归合计2,289 passed / 1 CUDA skip。主树整合回归与真实SDK CLI收尾
另行验证，不能以unit tracker或CPU bf16替代CUDA/真实代理验收。
没有执行真实 proxy、20,000 更新或 CUDA bf16 验收；D1–D6 尚未交付。
原 `V3StepTrainer`、性能模块和正在执行的 A/export 树均未修改。

## 范围与科学路径

`PrecisionPlan` 固定生产 endpoint 为 **20,000 次 optimizer update**，成员固定
fp32/bf16 × seed0/1。实际 consumed base samples 是另一时钟；未观察到有效标签
的批次消耗 samples 而不增加 updates，不能以 samples 或循环次数冒充 20,000。
sample budget 耗尽而未到 endpoint 属失败。严格消费已公开的
`current/configs/model_v3/performance/b_proxy_plan_v1.json`：生产验证更新网格为
**0,500,1000,…,20000**，validation noise seed=**0**、epoch=**0**。
初始未训练的0点也保存、纳入四成员曲线及checkpoint；恢复不重新验证已保存0点。
两个验证 role 分别保存，并显式声明各自源与用途：`VAL`、
`TRAIN_UNSEEN_CONFORMATION` 不因名字而自动获得 B 门槛资格。

训练复用 `V3StepTrainer` 的 S-only 路径，包括原 A4 三个 raw field 的
S 组内 observed-field 均值、clip=1、AdamW(lr=3e-4, betas=.9/.95,
weight_decay=.01)、按 consumed samples 的 cosine scheduler、每500更新
共享梯度探针与完整 sampler/provider/RNG 恢复。这是当前 V3 的 S 损失定义，
不冒充历史 weighted S runner 的 total loss。四成员共用这一固定定义；默认
性能选项直接消费已公开的 `b00_fp32.json`/`b01_bf16.json`，核对除 precision
之外完全相同；特别是 backbone checkpointing 显式为 true。V3 S语义在真实
production前仍须按指南由根协调者固定并绑定，不因合成执行链可用而默认采用。

选择性 bf16 直接复用既有性能 encoder：仅 QKV/QK/AV/projection/FFN 矩阵运算
使用 bf16；参数、坐标、距离偏置、RBF、归一化、最终 H0、S 头及损失保持 fp32。
没有在训练器外包裹全模型 autocast，也没有改原默认实现。

合成入口使用512维、1层、两个小分子/各两个人工构象，只为快速验证执行和
恢复，不能等同生产512×6或24万分子 proxy。每个返回结果及数值审计均保留
`scientific_acceptance=false`。

## 权威数据边界

`bind_authoritative_inputs` 只调用独立且 SHA 固定的 data-line adapter 的
`verify_and_bind_model_v3_precision_inputs(request)`。这是模型侧注入 hook，
不是 D5 物理 schema。adapter 必须按实际交付的 D5 和 TRAIN-only 规范核验
分子/允许构象、几何/原子身份、完整 VAL 与 TRAIN 未见构象人口、实际物理单位，
返回既有 typed `SamplingIndex`/`PreparedV3Batch` provider 与显式 S-only registry。
provider 须只读、节点本地，拥有已消费语义状态的 save/load 及实际关闭接口。
data-line 原始权威证明作为 opaque receipt 保存并绑定，不在模型侧重新定义
其字段或推断路径。两种验证人口各有独立固定 hash，验证实际输入/目标还再哈希。

模型侧向已 pin 的 hook 传入 `request.required_population`，明确要求 D5 的
**240000个TRAIN分子**、PM7、全部权威允许构象、先均匀分子再均匀允许构象、
禁止旧record前缀替代；还传入四成员相同 GPU 环境、实际 code/public prereg、
source inventory、CUDA/Torch/逻辑Python和控制签名的执行 binding。hook 必须
用实际权威文件核验，并将 opaque authority receipt 绑定到完整 request hash。
模型另检查 `len(index)==240000`：该index单位为分子，绝不拿构象/records数凑数。
这是一项未来真实adapter职责，当前没有构造任何240k fixture或物理schema。

每个role须有模型侧 `validation_role_sources`，逐项绑定population hash、purpose
及源authority。只有 `purpose=B_NUMERIC_GATE` 且 authority严格为已公开的
`proxy_TRAIN_only_molecular_inner_split_frozen_before_first_run` 才能进入B数值门槛。
至少须有一个这样的门槛人口；另一D5诊断role可标为 `DIAGNOSTIC_ONLY`，保留其
全部曲线但不参与B numeric_pass。外部VAL或其他D5人口不能静默顶替proxy TRAIN
分子内层验证。该mapping是模型自身的源用途receipt，不定义D5物理字段。

没有上述 hook、TRAIN molecule index 的 `authority=data_line` 或任一验证绑定
就早拒绝；没有旧 S record-prefix fallback，没有生成或宣布24万分子清单。
当前没有可用权威 adapter，真实路径仍阻塞，不能通过合成测试解除该阻塞。

## 验证单位、分母和门槛

每个验证字段保留原 loss、accuracy、MAE、R2（不适用时显式 None）、有效
标签数；回归额外直接累计 fp64 **SSE**。原单位 component RMSE 定义为
`sqrt(SSE/(N*target_width))`，vector RMSE 为 `sqrt(SSE/N)`。
对 A4 去噪，target_width=3，N 是原 valid atom mask 的有效原子数：

- component RMSE=`sqrt(SSE/(3*N))`，单位与原坐标一致；合成明确为 Å；
- vector RMSE=`sqrt(SSE/N)`，同一物理单位；
- eps_component_RMSE=component RMSE/sigma；原 A4 eps-MSE 分母为 `3*N*sigma²`。

RMSE 从原 prediction-target 的 SSE 累计，不从 field mean loss 或 batch mean
平均推算。两种 RMSE、sigma、unit、width、有效 N 与 component denominator
都保存。独立固定 validation seed 保护 CPU/CUDA/Python/NumPy 和 provider
状态，四成员验证相同 corruption/geometry/bond pair 人口；输入、实际 target、
mask、bond pair indices 和 choices 有内容 hash。

四成员聚合先拒绝 source/config/plan、role源用途、noise seed/epoch、单位/sigma/有效人口/验证输入 hash、
缺0点/缺 role/缺成员、配对 seed consumed clock 或 endpoint 不同，再对明确admitted
的proxy TRAIN-only内层门槛人口复用原
`bf16_curve_report`：每项数值曲线逐点处于两个 fp32 seed 包络内，原单位
component 去噪 RMSE 另外按同 seed 配对逐点相对差≤2%。不调整分母、不放宽
包络、不拿全局平均误差代替逐点判定；失败的原曲线同样保留。

数值报告自身不授予科学接受。根协调者还需独立验证 D5、所有 segment 的
source snapshot、真实 Slurm/supervisor C0、native offline SDK history/finish、
输入与实际 resource receipts，之后另作验收决定。

## 恢复、输出与 W&B

默认生产 checkpoint 网格为10000、20000更新，避免每500步保存一份完整
AdamW 导致超过原2GiB总预算。每个 segment 可显式 `--until-update` 提前结束，
在该更新边界再保存一个不可覆盖的 checkpoint。20k 所需长运行可分段恢复，
单段维持原 supervisor≤7200秒、child≤6900秒；不删除旧 checkpoint 来腾空间。
GPU≤85%、RSS≤56GiB、持久总输出≤2GiB及私有 scratch/cache 原上限不扩大。

新 bundle 在原 `V3StepTrainer.save` 的完整安全 checkpoint 外再绑定 member、
plan、全部源/数据/provider/精度配置、已完成验证点、update/sample/log clock。
`PRECISION_COMPLETE.json` 最后创建。恢复使用 `weights_only=True`；member/
配置/源或 runtime 不同、摘要不符、未完整的目录均拒绝。原 optimizer、scheduler、
CPU/CUDA/Python/NumPy RNG、sampler、provider 已消费状态和验证状态都恢复。
失败时保留最后已发布的 complete checkpoint，不拍摄执行一半的 optimizer
状态冒充安全恢复点；未 checkpoint 的尾部可能需从前一完整点重放。

每个 segment 使用 fresh outside-Git 输出根和 fresh **persistent offline W&B**
run。恢复采用显式新 lineage，保留 parent checkpoint 与原 tracker id/path，
延续 trainer log cursor；不向旧 SDK 文件追加，不依赖 offline resume 的含糊
行为。原生 SDK 每条 `commit=True` 之后写 fsync 的 JSONL mirror，finish 在
finally 中执行并记录首个 failure 与 cleanup 错误。mirror 不代替 SDK 字节验证，
也不宣称在线同步。真实权重和日志均在 Git 外。

## 可执行命令与尚缺验证

在根协调者分配的 CPU Slurm allocation（CUDA_VISIBLE_DEVICES 为空）中，
使用现有 chemprop Python 与 current/、tools/model_v3/、已验 deps 的 PYTHONPATH：

```bash
$PY tools/model_v3/run_precision_experiment.py member \
  --input synthetic --device cpu --precision bf16 --seed 0 \
  --updates 4 --validation-every 2 --max-batch-samples 2 \
  --until-update 2 --deterministic-controls \
  --code-sha "$CODE_SHA" --prereg-sha "$PREREG_SHA" --output "$OUT_FIRST"

$PY tools/model_v3/run_precision_experiment.py member \
  --input synthetic --device cpu --precision bf16 --seed 0 \
  --updates 4 --validation-every 2 --max-batch-samples 2 \
  --resume-checkpoint "$CHECKPOINT_FROM_RECEIPT" \
  --resume-output-root "$OUT_FIRST" --deterministic-controls \
  --code-sha "$CODE_SHA" --prereg-sha "$PREREG_SHA" --output "$OUT_RESUMED"
```

checkpoint 名字和log cursor以实际产物为准；包含两个role的0点后会有额外日志。
四个成员各自完成后执行 `report --members <四个member_result.json> --output
<fresh outside-Git JSON>`。report 仅是审计，不启动任何作业。

新增 CPU 测试实际执行 fp32/bf16 小 S 训练、完整/分段恢复模型/AdamW/RNG/
曲线逐位比较、u0真实checkpoint/恢复不重放验证、四成员含0点短训练、SSE 分母
以及authority/240k实际分子数/源用途/网格/endpoint/source协议拒绝。
尚待执行；不包含 CUDA 性能、真实 SDK durability 或20k科学验收。第一版未执行
草稿的错误默认值及原SHA已保留在`02_B_pre_review_source_receipt.json`；没有旧PASS。
