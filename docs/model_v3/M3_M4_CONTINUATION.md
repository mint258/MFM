# M3/M4 续接入口（2026-11-10）

状态：D6正式READY；M3 P三候选已实际启动。此页只说明执行接口，未选定主干、头、配方或B*。科学规则以DECISION_RULES_TASKBOOK_V2.md为准；原S结果、M2诊断和预注册保留。

统一入口 `tools/model_v3/v2_run_development.sbatch MODE CONFIG GPU_UUID PYTHON`，通过sbatch指定实际空闲节点。MODE为native_s、v31或dev，分别调用原v2_train_s.py、v2_train_v31.py、v2_evaluate_s.py；不替换训练算法或开发面板。新输出在 `/lfshome/zixiao/model_v31_20261105/`，先将其训练根追加到仓库外 `runs/model_v31_20261105/model_output_budget.json` 的roots；dev子目录共享该根。总预测仍全节点合计100GB，已分配物理块去重扣除。启动与运行保护沿用现有真实节点字节/inode、native quota及UUID锁；未注册根不运行。

native_s配置只含原CLI参数：index_path、output、distance_bias、views、seed、samples、batch_size、microbatch_size、lr、schedule、clip、workers，以及恢复时的resume。C1补seed1时继续读原S240k/records.parquet，6000000样本、B32/micro4、lr3e-4/cosine/clip1，原index与其他科学参数不变。旧configuration.json中的model/betas是生产器报告，不能作为未知CLI字段透传。v31配置直接使用原实验JSON。dev配置只含checkpoint、output及可选validation_index，固定原18格TRAIN内层面板。

待P的6381/6382/6383实际开发评价闭合后，与保留的S_C1_0_seed0_v2、S_C1_a_seed0、S_C1_b_seed0_v2的真实18格分数按每个seed内S/P等权汇总。仅初始前两候选各补S/P seed1；先完成它们的开发评价，再按同配置真实种子SD和既定简单性顺序确定C1。条件不能冒充种子，Bootstrap不能替代预训练种子SD。保持原失败记录及实际完整检查点的区别。

后继顺序及既定网格：C3两/三视图×S/SDP使用胜出C1；H1/H2/H3×P/D/SDP使用选定主干/视图；H1下注册表/可学习池化×P。每项初始seed0，前两配置各条件补seed1。完全相同科学配置与预算的已完成运行复用，不重训；未选择前不填默认胜者，也不释放原Held两视图旧任务。

M4依次为五个lr×S/P/B32、前两lr×S/P/B64、最佳lr下cosine/WSD（末20%线性衰减），再用实际TRAIN preclip范数p99确认SDP。全量S/P按D6正式TRAIN，保持完整64M调度预算，以run_until_samples分段取得1/2/4/8/16/32/64M开发读数；每段恢复原优化器/RNG/样本时钟。实际达到平台才决定B*；64M仅观测上限。最后冻结模型/配方两份配置、代码标签，并补全现有PREREG/HANDOFF。无下游TEST、性能网格、正式预训练或付费服务器运行。

本入口新增10项分派测试及2项共享输出注册测试，只验证既有CLI参数保留与同一预算登记；不增加实际模型冒烟或独立数据复核。实际测试结果记本日DAILY。
