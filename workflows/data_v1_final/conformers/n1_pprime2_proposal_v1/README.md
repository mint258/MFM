# N=1 的 P′第二个真实 UFF 候选提案

状态为 PROPOSAL_NOT_AUTHORIZED_TO_GENERATE。本目录只实现只读规划和纯
选择辅助函数/fixture；没有生成、优化、Slurm 提交器或生产科学运行入口。
Root 需要先审阅此方案是否兼容原指南，然后登记独立的新科学适配源码；
当前已冻结的配方、336试点源码/配置/prepared 和正式补齐源码不改变。

## 要解决的边界

原 PM7 N=1 的来源母群计数为 5040（planner 将现场对照，异数立即拒绝）。
这不是声称 5040 都属于最终 common：remaining FULL 必须排除，
UFF_UNSUPPORTED/原基线未闭合及最终 common=false 的分子也不能直接开算。
原 common 身份、PM7 N、原 S′baseline/count 和原顺序全部保留；
只额外建立 P′ parent 扩展视图，使其能够取两个**真实** UFF 几何。
原 P′每分子前2条件不放宽成1，不复制坐标、不删 N=1 分子。

方案建议：

1. 最终 frozen common 内 N=1、已接受一个 UFF baseline 的分子，各生成
   最多一个新增接受几何。新任务账本/候选来源独立，不能借正式 fill 的
   target=2 调用旧 process_task，因为它会违反 target==原 PM7记录数核验。
2. 新适配继续直接复用原 graph/ordered_graph/fix_stereo/check_geometry_stereo/
   proper fixed-map RMSD 函数，并重新核 source record、原子 z/order、
   atomSHA、graph/stereo；原已有 UFF 坐标/来源必须逐位保留。
   使用 ETKDGv3、enforceChirality、prune=-1、numThreads1、embed max200；
   无 embedding 时原 random-coordinate fallback；UFF maxIts2000、
   energyTol1e-6、forceTol1e-4，非 finite/不收敛/立体不符不接受。
3. 候选预算按**原 N=1**的 10N=10（全源最多 50,400 次优化），不是把 N
   偷改为2而扩大成20。必须对本次真实候选保留 seed、candidate_id、
   optimizer code、坐标/geometrySHA、原子身份与计算来源。
   建议新 seed 域 sprime-ETKDGv3-v1-n1-pprime2:，31位 SHA256 规则与原一致。
   此新命名域及 P′扩展视图是**待 Root 审阅的方案**，不能冒称旧指南已有
   独立 N1 扩充授权。独立域避免重用旧候选编号造成来源混淆。
4. 沿 select_fill(existing=[原1条],candidates=本次真实收敛候选,target=2,
   fixed_map_distance,threshold=0.5)。优先接受距已有 >=0.5Å 的最低能候选；
   若没有，则 maxmin 选实际最远候选并显式 below_dedup_threshold=true。
   不允许复制已有行作为候选；两个真实优化结果若落在同一势阱、RMSD<0.5，
   明确标记。这不保证有两个 RMSD 唯一构象。若没有第二个实际成功候选，
   状态 PPRIME2_UNRESOLVED，不伪造数据，不自动 retry，不直接把条件放宽为1。
5. 新表以 molecule_id/native_extra_conformer_id='n1p2:<seed>:<candidate_id>'
   为物理身份，opaque geometry_id 另域 uff_sprime_n1_pprime2:<SHA>；
   带 supplement_role='pprime_n1_second'、baseline_geometry_id、
   source_record_id/atom_order_sha256/geometry_sha256、候选原始文件 pin、
   original_N=1/baseline_count=1、seed/candidate_id/provenance/below标志。
   不写入 common 原有 UFF N 计数，另记 pprime_parent_available=2。
6. 独立 view_id='pprime_parent_expanded_v1' 合并 baseline+新增几何，用
   geometry_source='uff_sprime' 与原 selection.stable_key 相同定义、
   seed20261025；old conformer_id=0，新增 ID 使用上述稳定字符串。
   expanded_orders 提供 fixed_random|energy|diversity；能量 tie 用稳定 ID，
   diversity 从 min-energy 起 greedy maxmin。P′各排序取前2，opaque
   geometry_id 显式映射；baseline 的单构象原顺序和基线 common 不重写。

choose_second/expanded_orders 仅为纯选择提案的可测试实现，不能证明输入候选
确实被优化；未来新生产 adapter 必须在严格来源核验后调用，并将原始优化
事件与坐标持久化。没有该新 adapter、Root 科学 decision 和实际硬件准入，
不能开始生成。

## 预算依据与执行步骤

只读 planner 消费正式配置中的 perMol audit、冻结 ROUTINE roles 和实际
336 试点 review/accounting/复现结果。输出全源 N1 对账、TRAIN+VAL 前瞻清单、
稳定挑选的32分子拟试点、候选总量和 budget_evidence.json：

- 最大优化调用数=scope分子数×10；每候选最多2000 optimizer步。
  50,400×2000=100,800,000 是最多迭代步计数，**不是** core-hours。
- 提供粗情景 coreh=scope数×336试点实测最长单分子秒×真实分配开销/3600。
  336试点不是 N1第二候选实验，此外推明确 calibrated_n1_cost=false，
  不能声称时长上界或用它直接授权 full。
- Root 如批准，先对32个最终 common N1分子做独立实测，16CPU64GiB、
  节点14–19、4h、普通全用户声明内存85%、8GiB写前上限、200GB配额余量。
  当前外用户 MinMemoryNode=0 导致正式准入拒绝时等待；不沿33632GiB例外。
  32专用实测要有 parent AllocCPUS×ElapsedRaw、完整失败和每worker
  PID/startticks/任务数、candidate收敛/去重/补足分布和原始输出。
- 用 N1实际 size/rotbond/ring/element层的最慢实测及真实分配开销重估全量，
  每批 <=500分子/<=48h（建议8h且提前2h停止派发自然drain），超过预测1.5倍
  停派发留证；总预算 >500coreh需明确 Root review。
  未知启动/提交不得自动重试；失败保存后交 Root。既有 UFF 配方不改。

实际 CLI 只用于 Root node20 16CPU64GiB 的只读 Slurm；先整合本提交、
等实际336完整闭合，给新鲜普通提交 preflight。没有 UFF 动作：

    REPO=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository
    "$PY" "$REPO/workflows/data_v1_final/conformers/n1_pprime2_proposal_v1/plan.py" \
      --config "$REPO/configs/data_v1/conformers/n1_pprime2_proposal_v1.json" \
      --pilot-review "$PILOT_REVIEW" --root-preflight "$PREFLIGHT" \
      --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/n1_pprime2_proposal_v1/plan_v1

输出 proposal.status=PROPOSAL_REQUIRES_ROOT_SCIENTIFIC_REVIEW，
generated_or_optimized_geometries=0、production_science_runner_present=false。
准备科学前还必须与实际 frozen common 交集并绑定完整原 PM7 pointer、
原 accepted baseline、源 SHA/身份；前瞻清单不充当 common authority。

Root 在 compute20 已核依赖环境运行6个纯fixture：

    "$PY" -B workflows/data_v1_final/conformers/n1_pprime2_proposal_v1/test_proposal.py -v

覆盖0.5优先/真实maxmin below标记、无候选不复制、新seed/候选身份、
重复候选拒绝、扩展视图稳定顺序且旧行不变、粗预算不冒称专用实测。
纯fixture不运行 RDKit、UFF、LMDB、Slurm 或大源扫描。
