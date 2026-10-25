# 手动推进固定小试点的 CPU 链

本轮只新增 `materialize_next_v1.py`、`run_stage_v1.py`、`reduce_stage_v1.py`、`reduce_stage_equivalence_v1.json` 和本文；已登记的原10文件与中央runtime/policy/launcher/submitter均不变。原数学/标签/阈值不改。

Root整合/静态检查后，初始MAD0物化命令（node由Root选当时可用CPU节点2或8–19）：

```text
/share/home/zixiao/.conda/envs/chemprop/bin/python -B /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/labels/streaming_cpu_v1/materialize_next_v1.py --reduction /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/streaming_v1/reduce_med_r6_p32_v1/reduction.json --job 4520444 --node compute-0-17
```

脚本自己只查sacct及读小metadata：父作业必须COMPLETED/0:0/至少16CPU；除这个明示旧r6/4520444引导外，父作业必须是已授权CPU小scope，并且监控closure必须`COMPLETED_NO_MEMORY_DENIAL`、无denial/异常/信号、线程已闭合、同job/intent/scope/command。输入还须由该实际父command的output拥有，scan的plan/phase/query或reducer的input manifest逐项对齐，不能借另一C0作业认可一个文件。

进一步核对固定4251record/512molecule/16owner groups/146field/14task、原roles及coverage fingerprint。scan逐16receipt核owner ref、field/task记录守恒、相同ordinal digest和16真实PIDs，再从小counter汇总新增mask门；不读owner/scientific Parquet。reduction逐field核4251分母与mask fraction、16组/16worker、task总数，新增mask>1%或producer STOP即拒绝下一请求。当前人口含原TRAIN/VAL/FULL，全部原样扫描，拟合仍由既有代码只用TRAIN；不写成4251条都是TRAIN。

物化器只生成一次闭合收据、显式command数组，再调用中央`prepare_request`生成CPU请求/脚本，绝不sbatch/launch/自动重试或自动跟链。新名字为`dv1_label_<med/mad_round/mask>_cpu_v1`与对应`reduce`名；科学输出仍在原`artifacts/labels/streaming_v1`根下新的`scan_*_cpu_v1`或`reduce_*_cpu_v1`。任何同名控制文件、闭合收据、intent或输出已存在即停止，Root需审阅原证据；不覆盖。小ref上限2MiB，科学大正文不重新读取/hash。

初次MAD0的command指向单独`run_stage_v1.py`：同一32GiB allocation、同一中央monitor下先运行4个新CPU边界fixture并保存独立boundary JSON，再执行恰一遍MAD0源扫描；保存独立stage收据。测试失败或STOP不开始源扫描，不重复旧19/24/13套。driver不杀进程/不设强制timeout/不重试。后续轮次直接scan/reducer，每次Root亲自闭合并再次调用物化器。

中央`label_canonical_512`固定request wall7200，而旧CPU reducer的三参数guard默认3600。经Root同意，新`reduce_stage_v1.py`只从已验CPU reducer复制，将该guard调用显式加第四参数7200；内存/科学统计参数未动。附一项逆编辑原字节证明，物化器自己也要求新文件必须恰等于旧文件这一个替换。新链用这个入口，旧reducer原件不改。

后续使用方式：scan实际完成且CPU monitor闭合后，Root调用`--scan <新scan_manifest.json> --job <实际父job> --node <选择CPU节点>`准备一个reducer；reducer实际完成且monitor闭合后，调用`--reduction <新reduction.json> ...`准备下一refine或mask。精确MAD全部完成后才允许最终mask；mask reducer完成只写小试点闭合、不给下一job，不升级full或finalD4。所有新AST/metadata/driver检查与实际结果待Root执行，不预填PASS。
