# Native72 执行链复核与有限因果实验提案

SOURCE FINAL / STOPEDIT。本轮只读源码、53594B旧contract/小protocol和Root提供的小summary；未执行Python/AST/tests/SSH/Slurm/QM，未打开72raw、actual input/result、Parquet/LMDB或大科学report。没有确认能解释15项失败的确定源码bug；未改程序、关键词、seed、parser、容差或质量门槛。原因UNKNOWN，原15FAIL和2000/full HOLD保留；下一步是有限的有区分力的实验，不把HOLD当作任务终点。

## 已有真实证据，不再列成未知检查

- Root实际Alpha1884800 C0/18s：Main小副本 `control/secondary_cluster_20261026_v1/alpha_short_followups_v1/pprime_print_intervals_diagnosis_summary.json`，本child机器读核14184B/SHA `a414396d544968bf3fa94e88e0afe4e567e0a8465003c059ec1aedb6a23c6d58`。11pure PASS、两份原报告全SHA后15条必要不变量总norm²区间全不交；gradient还检查Gram。仅排除其声明的纯旋转+nearest-print模型，不证明SCF、程序或其他原因。summary明确newQM/UFF/raw-coordinate reads=0、scientific_PASS=false。
- 已读native793小summary：24保留调用的实际input/nativeSCF绑定成立，无显式SCF失败、无stored/nativeSCF metadata冲突；12个PM7自己的输出坐标匹配输入，6个xTB gradient有自身坐标证据，6个SP没有自己的输出坐标块。不能再把PM7 own frame、全部24的nativeSCF绑定写成尚未核验。
- 793小summary中三组xTB gradient/noisy-SP在同一臂的native energy token中心差（base对rotated）分别一致：01200493为`-1559/250000000000` Eh；01201800/UFF为`1007/250000000000` Eh；principal00112266为`-139/1000000000000` Eh。这是实际读到的配对旁证，不是新的energy容差或SCF因果结论。

## 源链逐段核对

下表V相对 `repository/workflows/data_v1_final/pprime/`；E为 `runs/phase1_wp5_20261011/scripts/wp5_engine_v3.py`；N为 `runs/phase1_dataset_rebuild_20261010/scripts/wp4_native_pilot_v4.py`，均是原contract冻结源。

| 接点 | 具体源码 / 已确认关系 |
|---|---|
| 分子、几何和case身份 | V `vector_audit/prepare_v1.py:72–109`：rid=`vector-audit:{mid}:{geometry_source}`，base/rotated共享同rid；4种条件×两臂再加translation。`:157–164` PM7与adapted UFF各自传相应坐标/符号/图；`:86` 用starting_id+len(cases)单调生成caseID。实际CPU版 `vector_audit/cpu_v1/prepare_cpu_v2.py:77–114,166–174` 保留这套函数与迭代关系。未见PM7/UFF坐标行互换。 |
| noise与R | V `vector_audit/math_v1.py:29–46`：seed从protocolseed/rid得到P；target=(clean+P)@R.T；perturbed任务传target−P。E`:138–153`与N`:307–337`都用完全同seed公式/PCG调用，再加同P一次。最终为target。companion的row后缀虽不同，但任务是非perturbed SP，renderer根本不加noise，直接用target。**原P预补偿正确，未发现重复扰动。** |
| 渲染和真实调用 | E`:140–155`与N`:325–341`同12位小数、同元素行、MOPAC flags=1、同keywords+THREADS=1；xTB同`native.inp`及`--norestart --parallel 1`和原task args。V `vector_audit/run_v1.py:48–69`执行前重render且核prepared各SHA；`:103–114`保留实际postcall输入。实际CPU no_mem入口V `cpu_auto_memory_v1/run_frame_v1.py`同一科学execute_case。没有证据表明hash核的是另一份输入。 |
| 独立scratch/进程状态 | N`:313,331–353`每次新建随机scratch、cwd明确、环境来自冻结config；调用前不从旧case复制restart。E`:56–98`每次初始化原模块、capture/deferred-cleanup；V run每call重置CAPTURED/CALL_SCRATCH/CAPTURE_ERROR并闭合worker。未见多case共享输出文件名的目录冲突。 |
| raw配对 | V `raw_archive.py:23,51–62,77–85`三元主键为(record_id,calc_type,execution_id)，execution_id是真caseID。共享rid不等于串包。Alpha bounded reader `frame_native_precision_alpha_v2/raw_reader.py:39–53`再核每call rawSHA/bytes；`:run.py:119–158,207–208`核唯一case/三元raw定位，病例集合必须等原72。 |
| parser链 | `wp5_parser_v2.py:46–59`只为PM7 HB做明确fallback，向量来自冻结base；base `wp5_parser.py:58–61,83–90`保留原native读取与明确stdout fallback。N`:383–411,452–462`先原parse，再按task限制字段；gradient任务故意不把dipole当正式目标，审计从原JSON独立读dipole。V `read_outputs_v1.py:41–47,51–82,85–98`采用atom-major 3N reshape/原gradient文件次序/JSON dipole与固定单位。已完成的原token→冻结parser bitwise链和793真实绑定继续有效。 |
| R/t和比较 | V `math_v1.py:39–45,73–93`两臂coords、vector都主动旋转`@R.T`，梯度同规则；translation是独立控制。V `evaluate_v1.py:96–124`按(mid,source,condition)配base/rotated，`:139–153`另比较同几何gradient/SP。未见行列转置、translation混入、任意重排/重拟合R。 |

E冻结SHA `53c09b68938ead8449f0da2ec7a03337df3125826080ece58fabe107cdd9f26b`；N冻结SHA `6943612b2fd6c3c7a492c08183f2328230469dea5113aadc613c32378cc79b59`。本轮读取的是这些源码，不是重新证明其实际binary行为。此前固定commit官方语义复核保留于 `native72_semantics_source_review_v1.md`：MOPAC atom-major/坐标轴有源码支持，xTB条件axis变换不能仅凭存在该分支推定本批走过。新不变量结果更排除了“只换正交参考系/仅分量符号排列”这一模型，继续搜索最佳R/P没有定位价值。

两项真实源码**防护边界**不应冒充原因：旧evaluate的dict赋值自身未单独拒绝重复group-arm；old measurement对缺postcall refs的`all([])`会真。但生成时caseID单调、case目录O_EXCL，且后续72输入/24真实保留调用的明确唯一绑定已补足相应证据；未观察到本批重复或缺输入。不得仅凭这两种理论输入就宣布找到了15FAIL原因。

## 最小可推进方案：先固定输入，再15次独立QA调用

建议直接准备一个**有上限的新因果QA scope**，不再泛加一轮“有没有轴/SCF/打印”的72扫描。以已有固定失败 `molecule_01200493 / pm7` 为唯一母几何，原case对为054/055 PM7_B、058/059 xTB perturbed-gradient、060/061 noisy-SP。该固定选择来自793已绑定摘要，未按新结果挑选。Root实际CPU从原manifest核6个源case/原程序input refs，绑定原source/version/environment；若任何字段或caseID不符，停止，不换分子。

三种原task各5个控制，共**15个调用**：

| 每task新QA臂 | 输入 | 用途 |
|---|---|---|
| B1、B2 | 两次独立新scratch执行**同一份原base实际程序输入字节** | 同字节输入的重放稳定性，并与原base比较 |
| R1 | 原rotated实际程序输入字节 | 是否在同版本/设置下复现历史两臂差异 |
| P1、P2 | 从base实际12位坐标token做精确proper signed-permutation `(x,y,z)→(-y,x,z)`；两次独立新scratch | P为0/±1整数矩阵，det=1，不做浮点一般角度旋转或12位重舍入；区分一般R输入序列化与可重复的方向依赖模式 |

保留非坐标字节、原row/rid、symbols顺序、MOPAC flags/keyword、xTB native.inp和全部argv；新execution_id/输出目录是独立QA身份，不冒用历史producer，不进入production onceledger/人口。gradient输入是**已实际渲染后的noisy坐标**；若复用原NATIVE.invoke，必须在新QA显式边界做相同P预补偿并在**调用前**要求rendered字节与冻结目标逐字一致，不能把actual noisy coords直接作为新的native clean coords再加P。若无法重render到精确字节，拒绝该适配，另用显式审查的薄exact-input invocation接原程序生命周期；不得静默算第二份noise。

所有15仍使用原MOPAC23.0.3/xTB6.7.1及binary SHA、原环境、keywords、200s原单调调用上限和1线程；不改SCF精度/收敛阈值或重启设置。真实合法CPU16、有限墙钟例如1200s（申请上限，不是预测），最大15active child，未完成保留TIMEOUT/UNKNOWN，不自动重试。用原每call raw16MiB/input64KiB/result8MiB及whole2GiB软件界，不改科学阈值；全部raw/实际输入/argv/PID/返回/原始SCF与native数字token留存，实际会计含失败/启动/cleanup。Main现有已证node13/provider链可作为候选资源来源，但须Root当次fresh审查、完整输出reservation+200GB和有效lease；不在login计算，不默认Alpha已有可用的同binary环境。

Root可先只做只读CPU“6源输入＋15目标字节清单”准备（0QM），并将全部literalpins和exact options交独立Root review；不会由本报告自动批准调用。actual input都是DATA，不登录节点/Windows读正文。

## 判读和修复边界

- B1/B2或P1/P2在同字节输入/同环境下超出原数字证据：说明观察到重放不稳定，已排除该对的新geometry/ID变化；仍不能仅据此命名SCF原因。保留完整进程/环境/原native收敛轨迹，定位到其真实变化点。
- B两次稳定、R重现失败、P两次协变：定位到一般角度/有限输入表示或方向相关数值路径的组合，**不能只凭此就断言12位序列化是根因**。下一步仅针对这一个固定case决定是否做独立输入精度因果对照，不能立即更改生产renderer。
- 同字节重复稳定而精确P仍破坏原向量不变量：排除该实验的一般角度输入舍入解释；若原native字段/inputs绑定都成立，问题已定位到原程序数值/属性计算链的方向依赖，需精确程序级修复或明确方法限制证据，不能靠转轴/排列parser或改tol“修复”。
- 原R重放未复现历史差异：这也是实际结果，说明历史/当前执行上下文或稳定性仍需核；不删除旧15FAIL，不用新单次成功覆盖旧报告。全部task/重复/原新成本和差异一并报告。

向量用既有原tolerance和两种旋转的明确矩阵，native interval仅诊断；SCF成功不等于等变，能量微差不等于因果证据。无论QA模式如何，都不自签2000/full。真正缺陷确认后仅在新独立namespace/原source inverse及真实小验证后接回P′，保持旧证据和版本边界。
