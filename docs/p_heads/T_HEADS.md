# 原子级新预测头与 PMA 消融

2026-11-17；状态：实现与分阶段验收进行中，尚无新臂质量结论。

## 固定协议与对照

T0直接复用主线 B3 seed0 的完整 3M 状态和已有 R1/R3，不重训。实际来源为 `configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/B3.json`；旧 `round2/B3.json` 中 B128/1.5M 不是本轮基底。原配置中的迁移恢复来源、attempt、旧GPU限定已从新臂移除；全量 TRAIN、B32、3M、A1、PMA、优化器、clip、step_overhead 和首32/1M/2M/3M保存策略保持。新输出及日志位于本研究NFS目录，不向主线结果表写入。

## T3 PMA 均匀权重

新增 `p_recipe.pma_uniform_weights`，默认关闭。仅将 PMA 从原子读取信息的 cross-attention 权重改为每个有效原子 1/N；padding为0。PMA 后续 query self-attention、残差、FFN、sum分支和所有参数保持原结构；不删除q/k投影。因此参数量与 B3 完全一致。下游仍读编码器H0。

生产者新逻辑单元测试在 compute-0-20 通过2项：有效原子均匀参考（atol1e-6、rtol1e-5）；padding替换为1e8后结果逐位一致；参数数量一致；默认关闭/显式False与原softmax公式逐位一致；相同state dict严格加载。实际 B3 完整 ModuleDict(structural,pd) 也已在CPU strict加载通过，clock为3M样本、93,750更新，见 `results/p_heads/T/B3_checkpoint_loading.json`。这证明对照可复用，不构成新臂科学结果。

T3训练/3M评价：待合规空闲卡分配。

## T1 原子注意力解码器

新增默认关闭 `p_recipe.atom_attention_decoder`。分子内8头注意力，q/k/v为512→256且无偏置，输出256→512；两个LayerNorm、512→512→512 SiLU FFN，两残差输出层零初始化。仅原子标量和pair头读解码结果，分子标量仍从原始H0经PMA、向量头保持原路径。既有grouped_fields执行开关保留，仅为对应桶传入解码原子特征。

新增解码器单元测试在 compute-0-20 通过1项（零初始化逐位identity与分子间隔离）；实际64 TRAIN样本冻结编码器、最多2000步逐头验收尚待进行。T1训练尚未启动。

## T2 物理约束头

冻结42,961条面板的13字段标签检查代码已准备；完成一次检查前不实现约束头。达到99.9%字段才启用，其余保留MLP。约束检查、FP64参考与求和数值测试、实际64样本验收和训练均待完成。

## 显著性与最终判定（尚未应用）

所有科学规则以冻结 `configs/p_heads/preregistration.json` 原文为准。各臂3M seed0相对B3以1000次配对bootstrap求95%CI；R3差≥0.06且下界>0判胜，差≤−0.06且上界<0判负。其他情况触发该臂seed1及共享一次B3 seed1；最终按两种子CI及预注册平均增益门槛判定。R1独立报告但不触发补跑；CYP及逐字段VAL原单位MAE仅作描述。当前没有分数、差值或机制结论，不能据单元测试采纳新头。

## 限制

新代码默认关闭；不接入主线或p-followup在跑任务。标签、mask、归一化及字段集合不改。T1/T2真实头部拟合能力和新训练质量尚未验证；GPU等待不视为科学完成。
