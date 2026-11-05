# 训练视图 v1 · 阶段5 P/D前冻结

纳入：原D2启用字段除下述排除项全部纳入，r73替换为原子对σ/π两列，共134个训练字段，已冻结。机器可直接消费的完整名单、数组列号和原字段ID见 `configs/data_v1/training_view_v1.json` 的 `fields`；组内启用字段等权，不做覆盖率检查或冗余筛选。

退化判定仅用固定50,000 TRAIN，VAL及留出构象不参与。众数按训练F32精确数值统计（±0合并），众数比例严格大于95%时排除；总体标准差小于 `1e-6*max(abs(mean),RMS)` 时排除，RMS是该字段有效TRAIN值的典型尺度。向量仅在原registry同一field_key内汇合分量；原独立分量字段保持独立。

r73定义（用户已明确批准）：按原pair_index行求和；S-SIGMA/P-SIGMA/D-SIGMA对应σ，P-PI/D-PI对应π；每列只汇总两端同属该对称性的条目。混合及δ块不属于这两列，原r73数值完整保留。所选项任一缺失则和为NaN，无项不补零；方向、自环和重复条目保持原求和口径。代码到σ/π的字典在JSON中。

排除r674全部六分量（任务书要求）。退化排除：
- `P.pm7_B.r39.d`：mode_fraction_gt_0.95。
- `P.pm7_anion.r190.d`：mode_fraction_gt_0.95。
- `P.pm7_cation.r259.d`：mode_fraction_gt_0.95。
- `P.pm7_octanol.r326.d`：mode_fraction_gt_0.95。
- `P.pm7_water.r393.d`：mode_fraction_gt_0.95。
- `D20.NumBridgeheadAtoms`：mode_fraction_gt_0.95。
- `D20.NumSpiroAtoms`：mode_fraction_gt_0.95。
