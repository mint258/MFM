# 原生 A1 全 TRAIN 冻结拟合

2026-11-21 22:24:15 CST。本页只转录原生产结果，不回读数值数组或重新拟合。

1194228个原TRAIN分子，每分子一个原允许构象；排列与构象选择用独立20261112 RNG。元素计数Z1–118含实际H，加不惩罚截距；ridge alpha=1、五折seed20261112。旧D20/D3定义、11-07 D4与禁用字段不改。

23个分子字段：12项残差、11项原目标、0项未解决。0.30≤OOF R²<0.999用冻结元素参考残差；其余保留原目标，只有残差派生位置尺度被拟合。原子SASA不参与A1。下表TRAIN截断比例是生产脚本对R1对应目标的±6统计；它不替代仍在运行的原生目标/原子项完整截断报告。

| 字段 | OOF R² | 目标 | 有效TRAIN | R1目标±6比例 |
| --- | --- | --- | --- | --- |
| D20.BertzCT | 0.9625375768229503 | element_reference_residual | 1194228 | 0.0011630944844703021 |
| D20.ExactMolWt | 0.9999999999314119 | original | 1194228 | 0.0014327247393295082 |
| D20.FractionCSP3 | 0.7600056557317704 | element_reference_residual | 1194228 | 0.0007058953566655613 |
| D20.HallKierAlpha | 0.9613413611199442 | element_reference_residual | 1194228 | 0.0005668934240362812 |
| D20.HeavyAtomCount | 0.9999999999978288 | original | 1194228 | 0.0014126280743710581 |
| D20.LabuteASA | 0.9996515982207809 | original | 1194228 | 0.0014436104328486687 |
| D20.MolLogP | 0.8304049946504635 | element_reference_residual | 1194228 | 0.000796330348978587 |
| D20.NumAliphaticRings | 0.16792478589879556 | original | 1194228 | 0.0005057660681209953 |
| D20.NumAromaticRings | 0.8751426565936744 | element_reference_residual | 1194228 | 0.0005317242603589934 |
| D20.NumHAcceptors | 0.854496523583978 | element_reference_residual | 1194228 | 0.00012057998975070087 |
| D20.NumHDonors | 0.25716104454044 | original | 1194228 | 0.001636203472033816 |
| D20.NumHeteroatoms | 0.9999999999767407 | original | 1194228 | 0.0016094079187558826 |
| D20.NumHeterocycles | 0.43217043738299243 | element_reference_residual | 1194228 | 0.00032322136141507316 |
| D20.NumSaturatedRings | 0.17690992809054462 | original | 1194228 | 0.0014720807082064732 |
| D20.NumValenceElectrons | 0.9999999999972828 | original | 1194228 | 0.0015281838978821465 |
| D20.RingCount | 0.7821547820360973 | element_reference_residual | 1194228 | 0.0007201304943444635 |
| D20.TPSA | 0.904981289550364 | element_reference_residual | 1194228 | 0.0008482467334545832 |
| D3.PBF_A | 0.5151556561811097 | element_reference_residual | 1194228 | 0.00020766553790398483 |
| D3.PMI1 | 0.4930915709430602 | element_reference_residual | 1194228 | 0.002737333239548897 |
| D3.PMI2 | 0.13354526802174338 | original | 1194228 | 0.004958852078497574 |
| D3.PMI3 | 0.14994460462844206 | original | 1194228 | 0.0050350519331316965 |
| D3.SASA_total_A2 | 0.9143873683006889 | element_reference_residual | 1194228 | 0.0019209062256118597 |
| D3.volume_A3 | 0.9992243924823322 | original | 1194228 | 0.0016437397213932348 |

完整冻结系数、归一化及原参数见[唯一生产参数](../../results/d_recipe/reference/D20_A1_parameters_20261121.json)。原路径：/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/full/native_stage1/reference/D20/label_parameters.json；训练消费路径：/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/reference/D20/label_parameters.json。

原4537571 COMPLETED0:0/85805秒，续算4537575 COMPLETED0:0/32秒，仅复用已关闭产物。R1 4537592于2026-11-21 22:12:23 CST在compute-0-7、GPU-9db54192-dd3f-3177-e56f-dcd161ff932c冷启动3M/seed0。拟合闭合不代表迁移胜出；终点R3配对比较、规定条件seed1与最终决定仍待执行，CURRENT_BEST未冻结。
