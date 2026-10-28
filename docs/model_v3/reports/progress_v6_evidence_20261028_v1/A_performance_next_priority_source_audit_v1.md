# 阶段1/2下一项 A 性能优化：只读源码与已闭合元数据审计

建议下一项是真实 Native S 的 A5“同一 logical batch 内 encoder 分块/减少填充”门，而不是重跑 all-on、auto-all-on 或 head-off 的20+500。9e代码已有完整 CLI 接线和静态配置，可直接复用原 paired 数值工具；尚未找到其真实 GPU20+500与R1闭合证据。先用 a00 的三个checkpoint均开启，单独改变 A5 layout，避免把未测 all-off 或失败 fused/TF32 混入。这不是已经测得加速或显存资格。

本次完整读指南阶段1/2、v25完整报告及9e相关源码、已存 Root closures/监督标量；没有执行 Python/AST/Git/SSH/Slurm、模型、SDK、科学journal/数组或目标读取，没有改任何旧源或报告。精确path/bytes/SHA见同名refs JSON及 bindings。这里只hash显式小文件，不做2000源Windows全树重哈希；未fresh查询会计。

## 已完成与仍缺：不能把旧报告的PENDING或新校准误读为新数值门

阶段1已有完整三卡实测：3090/4090/5090的4520365/366/367，原6×512+A4+S、2warm+20measured、九个代表trace、独立369分析及378汇总。机器baseline_summary含三父会计/原配置、同输入与填充/吞吐/峰值。dist MLP是代表样本中最大的已归因GPU计算组件，并占kernel busy并集一半以上；“主导全局显存峰值”没有被证明。不能因v25汇总保留“完整覆盖仍缺”就把阶段1原基线重做。优化后的逐卡各项/叠加结果仍是另一项未完成要求。

| 项目 | 当前真实数值与R1范围 | 下一缺口 |
| --- | --- | --- |
| A00及manual/auto all-on | 原三卡A00全20+500；9e manual3976、auto4551闭合；A00四R14567–70加4571速度报告0.9932396351 | 不重复；all-on校准不能填A1关闭checkpoint或auto最优 |
| a01 backbone-off | 4090原4520456完整20+500通过，源8ece/预注册61658，真实UUID ec788...；5090/546为85%容量负结果 | 原4090 R1/1338仍待资源；该旧完整门不应重跑。不能把8ece/该UUID的资格直接挪给9e/另一卡。3090等条件未闭合 |
| a02 distance-off | 5090/590实际85%容量失败，未形成完整20+500 | 当前设置的负结果保留；其它卡/新明确工作负载的真实完整门与R1仍缺。不能在同8M/同条件盲重试 |
| a03 head-off | 原5090/549完整通过、旧ABBA0.8661；新9e/4580实际C0/2445s，20+500最大前向/梯度/loss相对差均0，201216base | 新四R14587–90及CPU4591已C0：candidate/reference1.056032973846484，153.29317646→161.88264901 base/s。无需再跑该门；其余卡覆盖仍缺 |
| a04 all-off | 配置和消费代码存在，未见本轮实际完整GPU门/R1闭合 | 不能把关闭head或自动选中全开冒all-off；需真实相符容量/工作负载后再做新门 |
| a05 compile | 5090/525原固定批阶段CUDA OOM/85%负结果，无完整数值门 | 不重复相同失败条件；其它明确环境或后续预注册布局组合仍未测，编译/重编译和冷启动开销须真实报告 |
| a06 fused | 原457固定20过、500有477点越1e-3，1091真实梯度回放仍保留失败门 | 当前候选不采用，不再重复同500。其它卡未知不能推为均失败；A10等组合不能绕过已注册 requires_pass |
| a07 TF32 | 原589完整20固定门失败，未进入500 | 不降低阈值或直接跑R1授验收；其它卡条件仍未测 |
| A4 radius sparse | sparse代码已实现，但当前S原基线use_radius_mask=false | 直接启radius会改变原全局注意力，不能算当前S数学等价收益。若研究同一radius-masked参照须另明确同语义协议，不把此项从原指南删除 |
| A5减少填充 | 9e同logical batch chunks已实现，99专项及完整4145回归闭合；只见CPU机制证明，未见真实GPU20+500/R1闭合 | 是目前可独立推进的真实新A项；旧sampler重分桶探索不等于它的数学等价验收 |

head-off本次 R1测量窗 allocated峰值为14600138240B，对照5364701696B；不是下降的显存，也不是全TRAIN/global-max资格。一次ABBA的约5.6%观察不能称统计稳定提速、A1全关或自动最优。全TRAIN计数最大N712、21个singleton超过500k目标且前500未含全局最大；没有用计数公式代替GPU内存实测。v25仍写head-off500运行是其历史点时，以上采用新实际Root v2闭合及4591证明补正，不改原报告。

## A5现成调用链及精确边界

- current/configs/model_v3/performance/a5_logical_batch_chunks_v1.json：schema model_v3_performance_execution_v1、manual；padding.mode=logical_batch_chunks_v1、atom_bucket_width16、max_graphs_per_chunk32、max_padded_cost_per_chunk1000000。
- a_execution_runtime.py22–74、264–287 已接 --performance-execution 与其raw SHA；paired/single会各自绑定真实resident_models2/1、同seed/模型/data/workload与完整implementation源图。
- v3_performance.py235–274 经 prepare_execution 包装原backbone；v3_logical_batch.py49–67按桶/大小稳定排完整graph，105–146仅在已经生成全部views/noise/mask后分块encoder，然后index_copy恢复原H0行序。heads/loss仍接完整原logical batch，不逐chunk归约；不重采样、不丢record/singleton、保留原Parameter和state keys。dropout与跨graph BatchNorm拒绝。
- 不要使用 --atom-bucket-width 或 --exact-atom-sort 来替代此配置：它们是旧sampler重组，paired入口明确拒绝，因为会改变optimizer批人口/轨迹。A5这里保持原8M logical sampler和3views，仅改变encoder布局。
- 9e此入口限原RealCoordTransformerBackbone，并拒未审v3_architecture；不是C1-a/b、所有头策略或最终D5/D6训练容量的自动许可。单graph超chunk目标仍保留，目标不是硬件安全证明。
- 同输入的数学语义不保证原FP32逐参数门：GEMM形状/累加顺序可变，CPU近似close测试不能替代所有原输出、329 named gradients/None与500点的严格实测。
- auto_closed_profile只匹配exact UUID/name/实际容量、软件与控制、source/model/seed/data/workload、layout和resident数量的closed观察，并在每批核观测envelope。select_capacity按已声明记录顺序选首个相符，不是全策略最优搜索；超envelope拒绝，无自动降预算/drop/OOM重试。auto+compile+padding因缺编译chunk-shape容量证据明确拒绝。现manual/auto all-on和head-off均不能授A5容量。

## 最少执行，不另加一轮框架/QA父

1. Root将既有 paired/single/speed 原方法与上述固定A5配置、a00 all-True、seed0/native S/8M/3views、原B1+A4/原始manifest/snapshot、同C35/9e/public8147精确声明到一个新方法source/操作包并正常预注册发布。现A00/headOff薄SB/Rootdriver硬绑各自tuple/包/门，不能原封不动换env冒A5；只需机械换family/原配置rawrefs和真实新gate消费，不改模型/采样/monitor。新的操作公开ref/输出/现场quota与hold仍PENDING，不造final请求。复用99及4145已有同9e回归，不为未改数学再造前置测试父。
2. 一个真正A5 paired GPU父，原16CPU64GiB/2h、supervisor6900s/RSS56GiB/whole2GiB/private2GiB及全用户85%/MemAvailable/quota/UUID锁全保留。原20batch前向≤1e-5/全梯度≤1e-4、同seed500loss≤1e-3逐项执行，失败保留。这里 reference 是新A5真实比较的必要对照，不是再造一份独立all-on校准。
3. 仅完整通过后，四个原single A/B/B/A，2warm+20measured；同A5execution的候选2/3与原参照1/4、各自独立R1观察。原a_speed_report.py已有 --runs4 --supervisors4 --numeric-gate真实A5根 --output 接口，会核同data、完整20/500、真实layout/resolved flags与同输入。无需改speed算法，不能拿4580或旧3976门作A5数值证据。
4. 这六个实际SDK的原配置/role/500或22显式step、journal投影/last-value summary/EOF/native exit由现literal749/tap2/transport有界组件复用，同一必要CPU父顺序合批审计并跑原speed report；只增精确case/来源映射，不新增通用decoder/监控/QA层。之后每组≤3的明确选择同步，原SDK保留。不要sync-all，也不把远端finished/行数读回冒逐metric独立复验。

若A5通过且有实际布局容量/吞吐观察，再考虑A02或A01/all-off与A5的明确叠加新gate。这是新配置的真实比较，不能把旧8M失败洗成通过；单项/叠加、三卡各表和all-off/全人口容量仍需分别补齐。直接试all-off需预注册有限工作负载与相符实测，不能由head-off峰值或singleton算式授权。若更换logical batch rung，reference/candidate须共同绑定新条件，不自动迁旧数值/速度资格。

指南原阶段1/2的三卡逐项及叠加、GPU型号/批大小自动选择边界、compile/fused/TF32/sparse/padding全部实现和负结果、B类fp32/bf16各2seed×20k、每条验证包络和去噪RMSE≤2%仍全量保留。当前S可推进A5，不等待最终D数据；这不取消D3–D6真实验收，也不冻结A/B/recipe/HANDOFF或宣告0–7完成。
