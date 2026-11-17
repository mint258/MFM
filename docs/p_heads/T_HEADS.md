# 原子级新预测头与 PMA 消融

2026-11-17；状态：实现与分阶段验收进行中，尚无新臂质量结论。

## 固定协议与对照

T0直接复用主线 B3 seed0 的完整 3M 状态和已有 R1/R3，不重训。实际来源为 `configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/B3.json`；旧 `round2/B3.json` 中 B128/1.5M 不是本轮基底。原配置中的迁移恢复来源、attempt、旧GPU限定已从新臂移除；全量 TRAIN、B32、3M、A1、PMA、优化器、clip、step_overhead 和首32/1M/2M/3M保存策略保持。新输出及日志位于本研究NFS目录，不向主线结果表写入。

## T0 复用的描述性基线

已有B3的CYP行直接来自 `results/p_recipe/scores.csv` 中该resumed运行的3M条目；原单位VAL来自 `results/p_recipe/training/fixed_20261115_provisional_B_20261116_round2_B3_5090_resumed_20261117/VAL_original_units_3000000.csv`。109个字段的MAE、观察数和单位以及以下4条CYP记录已原样整理为 `results/p_heads/T/T0_B3_descriptions.json`；没有重评、重算或增加bootstrap。

| 读出 | CYP任务 | 原误差 | 相对随机参考的score（只报告） |
| --- | --- | ---: | ---: |
| R1 | 3A4 | 0.4 | 0.41666666666666663 |
| R1 | 2D6 | 0.5769230769230769 | 0.06250000000000014 |
| R3 | 3A4 | 0.4285714285714286 | 0.28571428571428564 |
| R3 | 2D6 | 0.5769230769230769 | 0.06250000000000014 |

新训练完成后，逐字段VAL直接取本线已有生产者 `CONTROL/runtime/results/p_recipe/training/<run>/VAL_original_units_3000000.csv`；CYP取 `CONTROL/scores.csv`，不重新读出或拟合。CYP始终排除在七任务主分之外。完整逐字段数表随上述小JSON及新臂对应描述表交付，不另写评价协议。

## T3 PMA 均匀权重

新增 `p_recipe.pma_uniform_weights`，默认关闭。仅将 PMA 从原子读取信息的 cross-attention 权重改为每个有效原子 1/N；padding为0。PMA 后续 query self-attention、残差、FFN、sum分支和所有参数保持原结构；不删除q/k投影。因此参数量与 B3 完全一致。下游仍读编码器H0。

生产者新逻辑单元测试在 compute-0-20 通过2项：有效原子均匀参考（atol1e-6、rtol1e-5）；padding替换为1e8后结果逐位一致；参数数量一致；默认关闭/显式False与原softmax公式逐位一致；相同state dict严格加载。实际 B3 完整 ModuleDict(structural,pd) 也已在CPU strict加载通过，clock为3M样本、93,750更新，见 `results/p_heads/T/B3_checkpoint_loading.json`。这证明对照可复用，不构成新臂科学结果。

T3训练已提交真实Slurm作业4535405（node0/3090、16CPU），使用独立冻结源码T3_source。依赖4535404仅用于等待同卡H前向释放GPU资源，同时等待足够CPU分配；不是等待H的科学判定。当前尚无新臂训练结果。

## T1 原子注意力解码器

新增默认关闭 `p_recipe.atom_attention_decoder`。分子内8头注意力，q/k/v为512→256且无偏置，输出256→512；两个LayerNorm、512→512→512 SiLU FFN，两残差输出层零初始化。仅原子标量和pair头读解码结果，分子标量仍从原始H0经PMA、向量头保持原路径。既有grouped_fields执行开关保留，仅为对应桶传入解码原子特征。

新增逻辑在 compute-0-20 共3项测试通过：零初始化逐位identity和分子隔离；原grouped pair路径与逐头参考（atol1e-6、rtol1e-5）；失败头回退原H0路由。后者使用可选 `atom_decoder_fields` 列表，在grouped桶中区分是否读取解码表示，避免未通过验收的头继续收到新表示。单元测试不代替真实头部验收。

实际64 TRAIN样本冻结编码器、最多2000步逐头验收尚待空闲GPU；T1正式训练未启动。

## T2 物理约束头

冻结42,961条面板的唯一一次检查已完成，结果见 `results/p_heads/T/label_constraints.json`。读取原缓存的TRAIN 39,220条和VAL 3,741条，使用原单位raw标签，仅在原mask及全部原子有效的记录上逐记录检验；未更改mask或补齐缺失。阈值为 `max(N×5e-5, 1e-3×Σ|y|)`，通过率门槛99.9%。不把模型训练归一化后的数值用于电荷守恒检查。

| 字段 | 有效记录 | 通过率 | 处理 |
| --- | ---: | ---: | --- |
| r68、r279、r346、r413、r668 电荷 | 各42,961 | 各100% | 启用约束头，待数值与逐头验收 |
| r210 anion 电荷 | 42,960（缺1） | 100% | 启用约束头，待验收 |
| r44、r45、r46 PM7 Fukui | 各42,960（各缺1） | 各100% | 启用求和投影，待验收 |
| r64 Mulliken | 42,961 | 99.2528107% | 保持原MLP |
| r712 f_minus | 42,932（缺29） | 77.7462033% | 保持原MLP |
| r712 f_plus | 42,932（缺29） | 77.8044349% | 保持原MLP |
| r712 f_radical | 42,932（缺29） | 78.1771173% | 保持原MLP |

面板电荷和的实测整数与预注册一致：anion −1、cation +1，其余0。没有根据结果修改阈值；四个不满足字段按预注册保留MLP，继续其余工作。此检查在T2模型代码实现前完成。

已为上述9个通过字段实现默认关闭的 `p_recipe.physical_constraint_heads`。每个电荷头为512→64→2 SiLU MLP，输出χ和u；J=14.3996+softplus(u)，以14.3996/√(r²+1)构造软化库仑矩阵，逐分子解带Σq=Q约束的(N+1)阶KKT系统。FP64组装、求解，输出转FP32。Fukui头为512→64→1 SiLU MLP，再按原单位做 `f=s+(1−Σs)/N`，保留负值。

约束只作用于原单位输出；`V31PDModel.output_parameterization`沿用B3的raw，之后由未修改的原 `pd.loss`/`grouped_v31_loss` 应用该字段既有D4/A1变换进入原loss。没有把归一化残差的和强制设成原单位Q。

3项新逻辑CPU测试已通过：Q=−1/0/+1的电荷解与独立NumPy FP64参考比较（atol1e-6、rtol1e-5）且电荷和误差≤1e-6+N×1e-6、反向梯度有限；Fukui投影求和误差≤1e-6且允许负值、梯度有限；自定义约束头在grouped_fields下正确跳过原MLP桶并执行。真实64样本验收和T2正式训练仍待进行。

## 逐头真实验收方法（待执行）

`tools/p_heads/t_accept_heads.py`使用实际B3 loader在同一全量TRAIN清单中固定取64个分子及其第一个允许构象。加载真实B3完整状态，冻结编码器，缓存两个32样本批次的H0；只为当前臂的新头及对应atom/pair MLP开放梯度，其余参数固定。T1的初始loss来自B3已有atom/pair MLP与新增零初始化decoder；这些MLP可随新decoder一起更新，没有为验收另行重置。T2的初始loss则来自新初始化的物理头。采用固定AdamW lr0.003、weight_decay0，不做超参数搜索。每个头以实际原loss为初值，首次降至初值1%以下即通过；最多2000次更新，同时受单项4小时限制。未观察到有效标签的头记录为未验收，不视作通过。

T1按通过头列表选择解码器路由，失败头读原H0；T2只保留通过真实验收的物理约束头，失败字段恢复原MLP。验收只更新本任务配置，不修改主线、标签或mask。运行入口先取得共享UUID锁，再核实实际显存准入，写入受NFS磁盘guard/watchdog保护。当前真实验收已启动，但尚未生成最终结果。若固定初始化与预算下不达标，则按预注册保守记为UNRESOLVED/回退；这不证明架构本身必然无效。不会依据中途结果重置、调参或重复验收。全无通过的臂记为缺失，不启动与T0等同的重复3M；部分通过则明确报告实际作用的头列表。

## 显著性与最终判定（尚未应用）

所有科学规则以冻结 `configs/p_heads/preregistration.json` 原文为准。各臂3M seed0相对B3以1000次配对bootstrap求95%CI；R3差≥0.06且下界>0判胜，差≤−0.06且上界<0判负。其他情况触发该臂seed1及共享一次B3 seed1；最终按两种子CI及预注册平均增益门槛判定。R1独立报告但不触发补跑；CYP及逐字段VAL原单位MAE仅作描述。判定辅助程序已实现但尚未应用真实新臂分数；其单种子门槛及两种子效果/方向边界2项CPU测试通过。当前没有新分数、差值或机制结论，不能据单元测试采纳新头。

## 限制

新代码默认关闭；不接入主线或p-followup在跑任务。标签、mask、归一化及字段集合不改。T1/T2真实头部拟合能力和新训练质量尚未验证；GPU等待不视为科学完成。
