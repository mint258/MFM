# TRAIN/FULL 分布及 VAL 来源核验

状态：既有闭合聚合已比较；用户已指定 ROUTINE 分子作为 VAL，实际角色清单待冻结。日期：2026-10-25T12:16:26.595008+08:00。

## 目的

回答当前 TRAIN/FULL 的分子数量与已保存分布有何差异，并记录用户纠正后的 ROUTINE 验证集权威。本报告的原分布对照仍成立，但整家族留出已被用户替代；本报告本身没有物化新 VAL 清单。

## 输入及哈希

- population_manifest: /share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/population/manifest.json; 6,767 bytes; SHA256 d21bae7f7b6c1dfbfe9342635ded80a55ddc05baba46ebfaa66cb7831866b96e.
- user_decision: /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/run_decisions_v2.json; 1,940 bytes; SHA256 f62f3938f3449a652dfa4f02b5dfc667f9e8f3efaecda73911828b582815fec2.
- heavy_atom_bins: /share/home/zixiao/descriptor_analysis/runs/pretraining_readonly_audit_20261023_v1/tables/s_population_marginals_v5/heavy_atom_bins.csv; 6,556 bytes; SHA256 9de748c9b2063444f7e7c78000def04f15dc6ecfd459cc2676c3572ce86648e6.
- element_presence: /share/home/zixiao/descriptor_analysis/runs/pretraining_readonly_audit_20261023_v1/tables/s_population_marginals_v5/element_presence_marginals.csv; 12,123 bytes; SHA256 0b6e0f65760373364680c47f4cf7effbe0277ba2e0e1d912ca4d3f431be59520.
- sprime_training_manifest: /share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/training_inputs_v1/manifest.json; 4,238 bytes; SHA256 2f69b672350744369b08c672b62e3d276487714abc97b766a12140ec5af59997.
- routine_arrow: /share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/training_inputs_v1/routine.arrow; 2,636,514 bytes; SHA256 29b153bd734dba010035af83cc76d80447c85b17c3da953cb77f2da1713e7e58.

机器结果：/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/sb1_population_review_routine_v1/population_comparison.json，SHA256 dc42bd2317c86261c7a7ac302c39ac7e42e5d32c58d1586468a8b0aee2cac27d。生产脚本：workflows/data_v1_final/export/review_validation_population.py，SHA256 d6a41dfe4bba336a7a079e0ea89745223865342e348836e0c356b8d5fa73fac4。这些为原 S′补齐前的 WP5 人口，不冒充共同人群 v1。

## 规则和参数

只读取六个小型输入（含 ROUTINE Arrow 的完整性哈希）；不解析 Arrow 的 ID 行，不扫描原 LMDB、科学 parquet 或分子明细。对每个角色与类别，核对各 availability 行重复携带的 population denominator 一致，再以该分母计算全人口比例。重原子组使用每分子的 canonical PM7 最大重原子数。元素每分子每元素计一次，边际可重叠。

TRAIN 为 1,206,608 分子／11,104,772 records；FULL 为 13,858 分子／127,082 records。TRAIN 分子数为 FULL 的 87.0694 倍。原 authority 只有 TRAIN/FULL；routine 是 FULL 内的监控子集。用户最新指定由该 ROUTINE 的分子成员定义本轮 VAL，不再从 TRAIN 新划家族。

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

### ROUTINE 验证集权威

用户已纠正此前家族信息，并指定 ROUTINE 用作验证集。原 population manifest 明确 ROUTINE 是 FULL 子集，共11,322条legacy records、7,610个分子；training_inputs_v1/manifest.json 精确绑定 routine.arrow 的路径、行数、字节数及SHA。本次实际核对该Arrow的字节哈希，但没有解析ID内容。

有效VAL以这7,610个 molecule_id 为单位，覆盖每个入选分子的全部可用PM7/S′几何；原11,322条record成员另保存 legacy_routine_member。不得把7,610个分子的其余构象改回TRAIN。原TRAIN成员保持，FULL中未入选的分子保留FULL。共同人群过滤后实际VAL数量须重新统计，不能把7,610当作最终已可训练数量。

Role-freeze入口为 workflows/data_v1_final/export/freeze_routine_roles.py。任务只读取 molecule_index.parquet 与 routine.arrow，按16个互不重叠分片统计、验证及输出molecule roles；不复制1,100万记录表。实际检查ROUTINE distinct counts、属于FULL、TRAIN/VAL分子ID及precomputed identity component无交叉。molecule_index无完整InChIKey或骨架字面列，因此该层零交叉只继承原WP5绑定manifest的三路identity_checks=0，明确不冒充新全表化学身份重扫。

已保存聚合仍不含TRAIN/FULL来源交叉分布或分子骨架分布。先前整家族VAL方案仅为被用户纠正的历史，不再查找或生成家族分类。

## 异常与处理

没有修改原角色，也没有将整个 FULL 自动改名 VAL。按用户最新指令，仅ROUTINE分子定义effective VAL，source_role仍保留FULL；完整角色清单由Root统一提交16CPU的Slurm任务后验收。VAL的所有构象须在TRAIN归一化和嵌套训练子集生成之前排除。

## 已知限制

本报告只比较现有预补齐人口的边际；共同人群筛选及 Se 例外后的分布必须另算。旧输入曾用 FULL/routine 作模型监控，不代表本轮已建立独立、未被使用的验证集。实际role-freeze尚待执行和验收，不声称D-5完成。
