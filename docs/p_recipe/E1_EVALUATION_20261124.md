# E1 评估与判定实现（2026-11-24）

只消费 USER_DIRECTIVE_20261123 注册的 k=1/2/5 新3M和原round4 F2自身3M；冻结A1+B3+B4+F2。`e1_readout_entry.py` 使用原I1受管运行器、原L6/H0特征及R3探针，R1交原CPU流程。新源校验只接受实际自身3M终点；默认I1调用保持原校验。

全量微调使用原四任务、三个微调种子和原scratch12。原F表的点估计与均预测CI继续分别保留；E1的判定区间使用与其点估计对应的“三个种子MAE均值 / 共同三个scratch种子MAE均值”所定义的改善。`E1_seed_mean_draws=true` 在首次主统计的同一组1000次分子抽样中保留该均值改善，不重采旧主统计、不用ensemble CI代替种子均值CI。每数据集所有任务共享同一整分子draw，按原seed20261025。四任务等权均值的1000个保留draw可在四格间配对；群组、scratch/reference绑定不一致时拒绝配对。

`e1_decision.py` 只对保留draw做代数，沿用原tau/CI规则。最小k必须frozen R3和full均非LOSS；缺失格明确列出。选中的k<10如有WIN，采纳前需条件seed1；P/S共同k仍待用户确认。不新增选择顺序、预算或阈值。

新逻辑验证4539400，CPU12、1核、8秒、COMPLETE0：3项合成测试通过，8份修改源AST通过。测试覆盖种子误差不能被均预测误差替代、分子配对身份、双读出共同选择及条件seed1、原预算/层/来源路由。未重跑4项cap测试或旧回归/旧结果。

k10 full主统计4539401在CPU12等待afterok4539396，启动时要求原12份完整微调摘要；输出仍原E1 NFS总32GiB预留。其余三格的36份full、3份GPU读出及3份CPU统计为ready=false草案，待真实3M完成后再绑定checkpoint字节/mtime和退出证据。
最终章节由e1_report.py消费闭合的E1_k_star.json生成，逐格列frozen R1/R3和full的Δ/CI/判定、实际平均k、每臂clip及四任务full MAE均值/std；不产生新的科学统计。消费者新增2项检查4539405 C0/1秒通过，缺失E1、缺失微调种子或未闭合条件seed1均不能生成最终REPORT。k10原主统计在4539401之后由4539406按原字节导出至results/p_recipe/E1/k10_full/，所有来源预测仍原封保留。

四格最终判定入口e1_decision_entry.py已准备，配置decision_seed0_draft.json保持ready=false。其输入须为真实自身3M、原L6/H0、全部48项full的原来源与闭合主统计；只对原1000个保留draw做配对代数，不重抽。新来源路由测试4539407 CPU12/1核/4秒C0，原3M接受、9M中点/改层拒绝；3份AST通过，root1813547 reap0/children=[]/实际不存在。若最小合格k有WIN且拟采用，输出WAITING_CONDITIONAL_SEED1，k_star不提前定稿。
