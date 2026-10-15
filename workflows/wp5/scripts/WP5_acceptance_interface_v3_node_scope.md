# WP5 验收接口当前节点修正 v3

原接口9499891f、wrapper1/2及各原Python源保留。实际接口改用 `wp5_acceptance_v3.sbatch`，科学验收仍exact200记录/2400任务，所有标签/精度规则、seed、原坐标、字典/参数、12方法输入不变。

- plan-200/compare-200 调用独立 `wp5_acceptance_recompute_v2.py`；plan显式runner7及 `--node-authority ROOT/gates/wp5_node_replacement_user_approved.json`、`--node-scope-plan ROOT/packing/node_assignment_v3/tasks.json`。生成计划记录二者真实SHA32b0…/dd195…，argv亦传入这两flags；仅元信息scope适配。
- recompute-200 使用 `wp5_acceptance_launch_v2.py`，除runner/protocol/dictionaries，再检查上述实际authority/scope SHA，不启动计划外科学任务。
- storage 使用独立 `wp5_acceptance_storage_v2.py`；delivery用 `wp5_acceptance_delivery_v2.py`，仅将六节点清空证据集合更新为12/13/14/17/18/19，storage附实际授权SHA。不把设计15/16当成实际hostname。
- catalog、verify_v2、pilot科学内容完全沿用原源；最终node/jobmap继续由Root实际authority给定。
- 当前wrapper SHA8d80c10bb073f8d16639c638d0390ce50e8e08fabb360d32437c506b78e94840；recompute2 1eb39b6e462ae79d3ec9a5bc4dc0dad9b046bb2351f0088648ffb44eaf4a1130；launch2 d245aeb9134833387f40d3baecaa19b1b9de30dfcf35f5e9ac1216266854edcf；storage2 b0079d607fca21384d7707f8c685bce1f912642fdf8584fa027df1aea98fb27d；delivery2 9a754ad29231c4357504f3c028547a5387a013cea06fb752fb0add4a44aaa967。

此节点授权不豁免G3容量或任何其余gate/200验收。Root最终G0可绑定这些验收源SHA；正式及200均未启动，本次无提交/科学扩测。
