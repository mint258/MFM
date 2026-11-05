# A数值实验的可选H0 checkpoint导出

实现状态：439相关32项CPU检查通过，442分支整树2,203 passed / 1 CUDA skip；
主树整合回归另行记录。旧A工作树、既有checkpoint和标准checkpoint.py均未改。
实际457完成20批与500更新，但fused轨迹未过门槛，按设计没有导出；不以失败
实验制造READY，不将CPU往返升级为真实native导出验收。

`paired_a_acceptance.py`新增可选`--export-candidate-checkpoint PATH`，默认关闭。
PATH必须是本次fresh `--output`根下的一个fresh直接子目录，保证权重和原子写入
临时文件都纳入原2GiB总输出预算。不会另建未计量的外部checkpoint根。

仅当真实native S、非smoke、20个固定批的逐输出/逐参数梯度门槛及500个更新的
逐步loss门槛全部通过，且原始stream/输入句柄与两个W&B SDK已实际关闭，才
进入导出。门槛、训练数学、RNG、采样、每步compute计时均不改变。dump和
验证位于科学计时之后，run_status另记scientific/finalization/export耗时。
generic bridge内部manual_seed也可能触及CUDA RNG；adapter在验证外层保护
CPU及所有可见CUDA RNG，并记录前后fingerprint相等，不修改原bridge。
科学门槛失败或cleanup失败均不创建已验收导出；导出中断保留失败证据，不发布
可用READY receipt。外层Slurm/supervisor终态仍需根协调者独立核验。

示例：在现有经审阅的单GPU supervisor命令中，child参数追加：

```bash
--deterministic-controls \
--export-candidate-checkpoint "$OUT/candidate_h0"
```

导出的是candidate在实际第500次更新后的参数，来源可为后续本来就要执行的
A01/fused等通过项；不是从现有未导出实验或历史384模型重构权重。不同提交的
科学来源另行绑定，不借旧A00或toy通过结果授予导出。

标准保存API没有environment provider注入点，且默认torch.__version__为
TorchVersion subclass。新`a_checkpoint_export.py`严格复用标准format_version=1
同字段结构、semantic_config/contract_hash/environment_fingerprint及原
`_atomic_torch_save` serializer，仅在本次新payload里将environment的Torch版本
转为plain str。原API、原文件字节和默认环境provider不变；没有unsafe pickle
fallback或safe-global名单扩张。CPU测试比较标准API字段结构，并直接使用
`torch.load(..., weights_only=True)`和现有generic `load_encoder_pair`读取。

产物包括：

- `candidate.pt`：标准format1、`model_state`、真实candidate optimizer state；
  scheduler_state明确记录未使用scheduler。checkpoint_type为A诊断H0-only。
- `model_configuration.json`：完整flat模型/训练语义，供generic bridge校验；
  runtime performance options与deterministic controls另列phase1 provenance。
- `a_run_configuration.json`与`provenance.json`：原始A配置、code/public prereg、
  逐源文件SHA、数据manifest/原snapshot、seed、options、控制签名、500步及
  实际已消费base-record clock/committed cursor，以及两gate和消费/history文件引用。
- `READY.json`：只有安全加载/严格shape/config/source核验和预算检查通过后
  创建，含供现有panel request使用的checkpoint/model_configuration/architecture
  bindings。状态明确为`H0_BYTES_VERIFIED_PENDING_OUTER_JOB_TERMINAL`，不能
  冒称尚未发生的Slurm完成；根协调者须再核对真实终态。

generic H0桥重建原factory的FP32 512×6模型，严格检查全部state keys/shape/dtype
及模型语义；它不恢复训练时的checkpoint/compile/fused执行路径。原始模型身份
与实际运行选项同时保留，避免把model.config_dict误当完整执行配置。H0定义、
原子顺序、512维接口不变。该导出不等于正式预训练收敛、最终panel结果或recipe冻结。

尽管标准格式保存真实optimizer，A诊断仍不支持resume：没有承诺可恢复RNG/
预取/lineage的训练器，CLI继续拒绝`--resume`，provenance明确H0-only。不能将它
改名伪装为old S runner或V3StepTrainer artifact。

CPU回归用真实512×6模型在两个小图上训练2步，仅测试安全序列化与H0往返，
不产生READY、不伪称native20+500或GPU验收；另检查默认不保存、失败不发布、
wrong shape/同shape不同config/错误source binding拒绝，以及旧标准源SHA不变。
