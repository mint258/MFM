# D′：当前最优M2上的构象分解（预注册）

依据[2026-11-17用户补充指示](USER_DIRECTIVE_20261117.md)。原D沿M1+C基底继续完成，D′新增独立seed0、3M，不等待D，不停止或迁移在跑任务。B/F64缺源与C/loss均结项，不排查缺源原因、不再处理冗余字段标准。

## 固定配置与验收

截至准备时配方线尚未发布CURRENT_BEST.json，采用指示明确指定的round3/M2.json（A1+B3/PMA+B4，gamma=0.1597693323500406）。原配置完整保存在configs/p_followup/M2_reference.json；Dprime_M2_seed0.json仅增加conformer_decomposition和运行名/路径，移除旧M2的attempt/resume/故障回退元数据以从seed0新初始化。其余执行键与M2相同，包括B32、14读线程、FP32、lr3e-4、自身cosine/2%warmup、3M、1M/2M/3M完整保存及自身固定clip校准协议。启动前再查看CURRENT_BEST。

使用完整109源字段/97物理损失项；33个已选字段复用D_parameters_accepted.json与D1全部split均值表，其余字段（包括C曾排除的10个字段）保留原目标。无D1重算、字段扩展、D2逐头验收或测试权重复用；sidecar保持关闭。配置层面相对于M2的科学差异只有构象分解。

PMA组合的实际单测发现初始化顺序会将双输出头覆盖回单输出；修复为先创建PMA头，再扩展选中头。扩展使用独立fork_rng，原输出第一行与未选头/PMA参数保持；默认关闭路径逐位一致。运行中D_source/75c598e保持冻结。本次实际compute-0-20单线程CPU测试：新增2项PMA组合测试与5项既有分解consumer测试全部通过（7 passed，0.16s）；不重复逐头训练验收。

## 判定（在D′读出前固定）

主要读出R3，复用M2的3M结果及原配对1000次MID bootstrap；同时报告R1，不改变既有评价。单seed0若|Δ|≥0.06且95%CI不跨0，按符号直接判定；否则本线仅补D′ seed1，M2 seed1复用配方线，不另训练。补跑后两seed的CI下界均>0且平均Δ≥max(0.03，M2两seed平均R3×8%)为win；两seed的CI上界均<0为loss；其余tie。未触发前不启动seed1。

同MID构象差原单位MAE报告D′对M2的全部109字段，用原冻结VAL构象对，仅描述。工作A在同一5000 VAL集合补D′几何（CVF、CVF_res）。配方线C3完成后仅取已有分数，并计算第6层几何，与M2/D′并列描述，不加训练或推断检验。既有M2几何若与该面板/方法相同则复用，避免重复前向。

## 资源与顺序

D′仅一条3M，初估9–15 GPU-h；仅条件触发时另加seed1。提速线待完成的GPU工作优先，其次配方线，随后本线与head线；只准入现场可用卡。沿用共享UUID锁、按需CPU、非exclusive、实际节点字节/inode/UID配额守卫；CPU不够而合格GPU空闲时用既有SSH→sbatch完整状态接管。禁止node21和付费服务器。

现有NFS总峰值18GiB仍覆盖：保留C/D历史产物、D′及条件seed1检查点/评价、代码与历史scratch、均值表≤1GiB；新增D′产物预计≤1.5GiB/seed。原C/D≤4GiB子预算保持，D′最多另3GiB仍在总18GiB内。实际目标节点预检后才写入，不复制数据或权重，不删除旧输出。结果与资源成本按阶段推送，尚无D′胜负结论。

## 当前最优核对与实际保存（2026-11-17 17:00 UTC）

启动前实际读取配方线CURRENT_BEST.json，指向M2、seed0、3M，R3=0.4680026331456454、R1=0.2974547347686018；与本配置基底相同。D′冻结源码0da71c9，实际在compute-0-22/RTX5090（UUID9b6008d0）原生启动，PID17416/UID1278/start_ticks5287859/PGID17416，准入699/32607MiB；同任务接管4535717排队。

本线启动前只核对了实时队列，未确认提速线GPU必做项完成，优先级处理有误。已通过原有SAVE_AND_EXIT请求纠正：在5760样本/180更新完整保存，ACK与原生exit0一致，实际PID已退出，显存恢复699MiB；同任务4535717在PENDING/0秒状态hold后取消。原D4535660始终继续。完整模型/优化器/样本时钟/采样与CPU-CUDA RNG及clip统计全部由既有保存出口保留，回退量0；累计原生GPU占用139.199761秒（0.0386666003 GPU-h）计入成本，不以3M完成表述。

续接配置Dprime_M2_seed0_continued.json已指向该完整5760点，剩余预算由原3000000样本时钟决定。优先级仍为提速GPU工作、配方线、本线与head线；高优先级需要尚未满足时不再争用空卡。后续从原状态续接，不新初始化、不重算D1或重做D2，不因CURRENT_BEST之后变化而改已经启动的M2基底。

后续工具已按本指示准备：compare_dprime.py复用配对抽样并执行条件seed1规则（2项边界单测通过）；val_conformer_mae.py增加Dprime/M2模式，仅将同一既有VAL流程的字段数由99改为109，原D/C模式仍保留；directive_geometry.py只补Dprime/C3的第6层CVF和CVF_res，直接复用head线H1对M2同一5000MID/47698构象的已关闭几何。新几何不加PCA或方向性检验，C3分数仅引用配方线既有R1/R3。实际计算仍等待相应精确3M检查点。
