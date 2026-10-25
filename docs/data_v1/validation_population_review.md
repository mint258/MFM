# TRAIN/FULL 分布及 VAL 来源核验

状态：既有闭合聚合已比较；VAL 家族权威待定位。日期：2026-10-25T12:04:38.162383+08:00。

## 目的

回答当前 TRAIN/FULL 的分子数量与已保存分布有何差异，并为用户指定的“从较大人口中整家族留作 VAL”提供来源依据。本报告没有建立新 VAL。

## 输入及哈希

- population_manifest: /share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/population/manifest.json; 6,767 bytes; SHA256 d21bae7f7b6c1dfbfe9342635ded80a55ddc05baba46ebfaa66cb7831866b96e.
- heavy_atom_bins: /share/home/zixiao/descriptor_analysis/runs/pretraining_readonly_audit_20261023_v1/tables/s_population_marginals_v5/heavy_atom_bins.csv; 6,556 bytes; SHA256 9de748c9b2063444f7e7c78000def04f15dc6ecfd459cc2676c3572ce86648e6.
- element_presence: /share/home/zixiao/descriptor_analysis/runs/pretraining_readonly_audit_20261023_v1/tables/s_population_marginals_v5/element_presence_marginals.csv; 12,123 bytes; SHA256 0b6e0f65760373364680c47f4cf7effbe0277ba2e0e1d912ca4d3f431be59520.
- sprime_training_manifest: /share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/training_inputs_v1/manifest.json; 4,238 bytes; SHA256 2f69b672350744369b08c672b62e3d276487714abc97b766a12140ec5af59997.

机器结果：/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/sb1_population_review_v2/population_comparison.json，SHA256 e434d097dfcf2ca6bfd4ffbfe345fcf381041b59ef41e62084ce546d6ff7c720。生产脚本：workflows/data_v1_final/export/review_validation_population.py，SHA256 843d902227d716a9c046661d8d641112c4ec76b21a50ffe67d03cb1cae54920a。这些为原 S′补齐前的 WP5 人口，不冒充共同人群 v1。

## 规则和参数

只读取四个既有小型元数据/CSV；不扫描原 LMDB、科学 parquet 或分子明细。对每个角色与类别，核对各 availability 行重复携带的 population denominator 一致，再以该分母计算全人口比例。重原子组使用每分子的 canonical PM7 最大重原子数。元素每分子每元素计一次，边际可重叠。

TRAIN 为 1,206,608 分子／11,104,772 records；FULL 为 13,858 分子／127,082 records。TRAIN 分子数为 FULL 的 87.0694 倍，是用户要求的较大来源人口。原 authority 只有 TRAIN/FULL；routine 是 FULL 内的监控子集，不能视为独立 VAL。

## 统计结果

### 重原子数

|类别|TRAIN 分子数|TRAIN %|FULL 分子数|FULL %|FULL−TRAIN 百分点|
|---|---:|---:|---:|---:|---:|
|0_10|19,228|1.5936|208|1.5009|-0.0926|
|11_20|255,822|21.2017|2,868|20.6956|-0.5061|
|21_30|581,684|48.2082|6,510|46.9765|-1.2317|
|31_50|316,907|26.2643|3,888|28.0560|+1.7917|
|51_75|30,050|2.4905|350|2.5256|+0.0352|
|76_100|2,466|0.2044|32|0.2309|+0.0265|
|above_100|451|0.0374|2|0.0144|-0.0229|

既有分箱的描述性 total variation 为 0.01853412。FULL 在 31–50 重原子组的比例较高，在 21–30 组较低。这是可观察的边际差异；没有进行等分布假设检验或把它写成全部联合分布结论。

### 元素出现率

|类别|TRAIN 分子数|TRAIN %|FULL 分子数|FULL %|FULL−TRAIN 百分点|
|---|---:|---:|---:|---:|---:|
|H|1,205,878|99.9395|13,844|99.8990|-0.0405|
|B|89,919|7.4522|1,099|7.9304|+0.4782|
|C|1,206,013|99.9507|13,848|99.9278|-0.0228|
|N|956,592|79.2794|10,784|77.8179|-1.4616|
|O|1,111,731|92.1369|12,800|92.3654|+0.2285|
|F|183,239|15.1863|2,035|14.6847|-0.5016|
|Si|353,578|29.3035|4,580|33.0495|+3.7460|
|P|14,528|1.2040|171|1.2339|+0.0299|
|S|353,559|29.3019|3,886|28.0416|-1.2603|
|Cl|188,900|15.6555|2,071|14.9444|-0.7110|
|Se|24,396|2.0219|287|2.0710|+0.0491|
|Br|69,313|5.7445|738|5.3254|-0.4190|
|I|15,560|1.2896|210|1.5154|+0.2258|

例如 FULL 的 Si 比例较高，而 N、S 比例较低。不同元素行存在重叠，不相加推算不重复分子数。

### 来源、骨架和“九十几个家族”

本次已保存聚合不含 TRAIN/FULL 的来源交叉分布或分子骨架分布，尚不能报告这些维度的实测差异。已检查 docs/phase1/ 顶层文档、审计报告、workflows/dataset_rebuild/scripts/、workflows/screening/scripts/ 与审计脚本中的分类/聚类/骨架线索，尚未识别可用的约九十个分子家族权威清单。账户94个顶层目录、65个存储组、13个WP5家族及下游 scaffold folds 均不是所需的分子家族。

下一步应优先取得原分类清单和生成规则，并在有界 CPU Slurm 作业内只投影 molecule ID、原家族 ID、角色、身份键及必要结构列：检查一分子一家族/多家族规则、TRAIN/FULL 家族分布、家族大小、跨家族身份重叠及约定的去泄露键。未定位原分类前不另造新分类并称其为历史约九十个家族。

## 异常与处理

没有修改原角色，也没有将 FULL 自动改名 VAL。用户已要求差异存在时以较大人口作来源，因此候选来源为 TRAIN；具体家族 ID、完整成员清单与占比仍须权威分类支持后冻结。VAL 的所有构象必须随分子一起隔离，并在归一化和嵌套子集生成之前排除；既有 FULL 保留原角色。

## 已知限制

本报告只比较现有预补齐人口的边际；共同人群筛选及 Se 例外后的分布必须另算。旧输入曾用 FULL/routine 作模型监控，不代表本轮已建立独立、未被使用的验证集。未确定家族 ID，不输出训练可用的 VAL 清单或声称 D-5 完成。
