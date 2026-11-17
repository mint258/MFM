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
