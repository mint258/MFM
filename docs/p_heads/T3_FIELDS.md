# T3 生产者描述性字段附表

运行：`p_heads_T3_seed0_attempt2`。直接转录既有3M生产者记录，没有重新评价、拟合、bootstrap或计算MAE。

CYP来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/scores.csv`。CYP不进入七任务主分。

| 读出 | 任务 | 原误差 | 随机参考误差 | score | 排除主分 |
| --- | --- | ---: | ---: | ---: | --- |
| R1 | cyp.3A4 | 0.37142857142857144 | 0.6857142857142857 | 0.4583333333333333 | True |
| R1 | cyp.2D6 | 0.5 | 0.6153846153846154 | 0.18750000000000006 | True |
| R3 | cyp.3A4 | 0.48571428571428577 | 0.6 | 0.19047619047619035 | True |
| R3 | cyp.2D6 | 0.46153846153846156 | 0.6153846153846154 | 0.25 | True |

逐字段原单位VAL来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/runtime/results/p_recipe/training/p_heads_T3_seed0_attempt2/VAL_original_units_3000000.csv`。

| 字段 | 原单位MAE | 观察数 | 单位 |
| --- | ---: | ---: | --- |
| P.pm7_cation.r265.y | 1.5546740948814841 | 2000 | Debye |
| P.pm7_water.r399.x | 0.29374076031555885 | 2000 | Debye |
| P.pm7_water.r396.value | 2.113030967570311 | 2000 | A^2 |
| P.xtb_fod.r537.value | 0.0007052299870518066 | 106325 | e |
| P.pm7_B.r43.value | 1.835774036518862 | 2000 | A^3 |
| P.pm7_anion.r210.value | 0.015246467639533296 | 106325 | e |
| P.pm7_B.r45.value | 0.012555502706496713 | 106325 | e |
| P.pm7_octanol.r332.z | 0.19204031693167053 | 2000 | Debye |
| P.pm7_octanol.r343.value | 0.0534007352779081 | 2000 | eV |
| P.pm7_B.r63.value | 0.06306429049829604 | 2000 | eV |
| P.pm7_B.r54.value | 288.41328070886647 | 2000 | eV |
| P.pm7_B.r47.value | 0.36466175057391775 | 2000 | kcal/mol |
| P.xtb_ALPB_octanol.r460.value | 0.0033865119323894213 | 2000 | Eh |
| P.xtb_singlepoint.r668.value | 0.003744706239329525 | 106325 | e |
| P.pm7_B.r55.electron_nuclear | 1.8783202872495217 | 106325 | eV |
| P.pm7_B.r48.value | 0.4295638217105235 | 2000 | kcal/mol |
| P.pm7_octanol.r332.y | 0.21749200268578717 | 2000 | Debye |
| P.pm7_B.r84.value | 0.005545504149789673 | 106325 | bond-order population |
| P.pm7_B.r44.value | 0.014789569921969194 | 106325 | e |
| P.xtb_singlepoint.r669.y | 0.18123234529859475 | 2000 | Debye |
| P.pm7_B.r62.value | 0.09198997071685193 | 2000 | kcal/mol |
| P.pm7_B.r55.total | 0.7762250893182707 | 106325 | eV |
| P.xtb_singlepoint.r670.value | 0.0033447895835686907 | 2000 | Eh |
| P.pm7_octanol.r329.value | 2.11258701226848 | 2000 | A^2 |
| P.pm7_anion.r190.p | 0.014850084913525333 | 106325 | e |
| P.pm7_B.r52.x | 0.23886700470594951 | 2000 | Debye |
| P.pm7_B.r82.charge_density_q_minus_Z | 0.3345388201255709 | 54838 | e |
| P.pm7_water.r393.p | 0.007523880545851373 | 106325 | e |
| P.pm7_cation.r265.z | 1.3850019430893008 | 2000 | Debye |
| P.pm7_B.r58.value | 0.08337198217435365 | 318975 | kcal mol^-1 A^-1 |
| P.pm7_B.r50.value | 0.11703213095664979 | 2000 | eV |
| P.pm7_B.r56.K | 0.010419448695772427 | 798283 | eV |
| P.xtb_vipea.r751.value | 0.06720089639301527 | 1999 | eV |
| P.pm7_cation.r259.s | 0.006721545522588016 | 106325 | e |
| P.pm7_cation.r279.value | 0.0170847413733612 | 106325 | e |
| P.pm7_B.r42.value | 2.1136993417557877 | 2000 | A^2 |
| P.pm7_B.r56.J | 0.02428922887147972 | 798283 | eV |
| P.pm7_water.r410.value | 0.05493070538867323 | 2000 | eV |
| P.pm7_B.r56.total | 0.03725568861995836 | 798283 | eV |
| P.pm7_B.r52.z | 0.15616474879595263 | 2000 | Debye |
| P.pm7_B.r40.value | 0.0028028890789441934 | 798283 | bond-order population |
| P.xtb_singlepoint.r672.value | 0.09584660167898983 | 2000 | eV |
| P.pm7_B.r83.value | 0.07809155316839139 | 2000 | eV |
| P.xtb_singlepoint.r669.z | 0.16443701183551457 | 2000 | Debye |
| P.pm7_B.r60.value | 1.8474640889888503 | 2000 | kcal/mol |
| P.xtb_singlepoint.r677.value | 0.004479868106423082 | 118841 | bond-order population |
| P.pm7_B.r39.s | 0.0030812570360893646 | 106325 | e |
| P.pm7_B.r46.value | 0.010883301367055563 | 106325 | e |
| P.pm7_anion.r196.y | 1.4202063365239883 | 2000 | Debye |
| P.xtb_ALPB_octanol.r459.value | 0.0004795129967118083 | 2000 | Eh |
| P.pm7_water.r413.value | 0.006797387476768803 | 106325 | e |
| P.pm7_B.r52.y | 0.17677309587382478 | 2000 | Debye |
| P.pm7_water.r399.z | 0.20538549211987991 | 2000 | Debye |
| P.pm7_B.r68.value | 0.006703337983682882 | 106325 | e |
| P.pm7_water.r398.value | 0.024839144371650662 | 2000 | eV |
| P.pm7_B.r41.value | 288.5281734734816 | 2000 | eV |
| P.pm7_B.r64.value | 0.009202662571047033 | 106325 | e |
| P.pm7_B.r55.electron_electron | 0.55442650722751 | 106325 | eV |
| P.xtb_singlepoint.r671.value | 0.0666412205696106 | 2000 | eV |
| P.pm7_B.r49.value | 0.13046737591238344 | 2000 | eV |
| P.xtb_ALPB_water.r499.value | 0.0033830053928265366 | 2000 | Eh |
| P.xtb_singlepoint.r667.value | 0.02922308707949192 | 106325 | bohr^3 |
| P.pm7_water.r393.s | 0.00297400107810897 | 106325 | e |
| P.pm7_B.r53.value | 0.1934650914909437 | 2000 | kcal/mol |
| P.pm7_B.r39.p | 0.0074871008898716885 | 106325 | e |
| P.pm7_B.r82.Dn | 0.04305477099328545 | 54838 | 1/eV (source-dimensional inference) |
| P.xtb_vfukui.r712.f_radical | 0.001880566847238917 | 106147 | e |
| P.pm7_octanol.r326.s | 0.0029413138101893033 | 106325 | e |
| P.pm7_cation.r262.value | 2.111999915129072 | 2000 | A^2 |
| P.pm7_cation.r273.value | 3.345242974954499 | 2000 | kcal/mol |
| P.pm7_water.r397.value | 1.8357829538179038 | 2000 | A^3 |
| P.pm7_B.r56.EN | 1.1677547197124607 | 798283 | eV |
| P.pm7_cation.r259.p | 0.01596477232328617 | 106325 | e |
| P.pm7_anion.r190.s | 0.006252776847400302 | 106325 | e |
| P.pm7_anion.r196.z | 1.2119220339233288 | 2000 | Debye |
| P.pm7_B.r56.EE | 0.44078518816581175 | 798283 | eV |
| P.pm7_anion.r193.value | 2.1120318874257453 | 2000 | A^2 |
| P.pm7_anion.r204.value | 3.771702838295052 | 2000 | kcal/mol |
| P.pm7_octanol.r326.p | 0.007574607853241424 | 106325 | e |
| P.xtb_ALPB_water.r498.value | 0.0008159393698121343 | 2000 | Eh |
| P.xtb_singlepoint.r669.x | 0.2539406988537521 | 2000 | Debye |
| P.pm7_octanol.r331.value | 0.019506737870732527 | 2000 | eV |
| P.pm7_octanol.r341.value | 0.06169224715232849 | 2000 | eV |
| P.xtb_singlepoint.r666.value | 0.2252769013947104 | 106325 | Eh bohr^6 |
| P.xtb_fod.r538.value | 0.01465124699996681 | 2000 | e |
| P.xtb_vfukui.r712.f_plus | 0.0026095179595860903 | 106147 | e |
| P.xtb_vipea.r752.value | 0.045387404032979625 | 1999 | eV |
| P.pm7_cation.r263.value | 1.835224593642699 | 2000 | A^3 |
| P.pm7_B.r56.NN | 0.5487438438773276 | 798283 | eV |
| P.pm7_octanol.r340.value | 1.831234371372017 | 2000 | kcal/mol |
| P.pm7_B.r82.De | 0.03908763225909297 | 54838 | 1/eV (source-dimensional inference) |
| P.pm7_water.r408.value | 0.0636161732673645 | 2000 | eV |
| P.pm7_B.r56.C | 0.024716261385140614 | 798283 | eV |
| P.pm7_water.r407.value | 1.8390610306339223 | 2000 | kcal/mol |
| P.pm7_B.r65.value | 0.00285138245632797 | 797785 | e |
| P.pm7_octanol.r346.value | 0.006735292606067135 | 106325 | e |
| P.pm7_anion.r196.x | 3.0163896048110472 | 2000 | Debye |
| P.pm7_anion.r194.value | 1.83592124157213 | 2000 | A^3 |
| P.pm7_B.r61.value | 0.0653600013256073 | 2000 | eV |
| P.pm7_B.r73.value.pi | 0.03305610972088738 | 197626 | bond-order population |
| P.pm7_cation.r265.x | 3.4501374387855175 | 2000 | Debye |
| P.pm7_B.r73.value.sigma | 0.08583075836209213 | 599051 | bond-order population |
| P.pm7_octanol.r330.value | 1.8351034659085927 | 2000 | A^3 |
| P.xtb_vfukui.r712.f_minus | 0.0025893221808757937 | 106147 | e |
| P.pm7_octanol.r332.x | 0.28499348083557563 | 2000 | Debye |
| P.pm7_water.r399.y | 0.23135955240996556 | 2000 | Debye |
| P.xtb_perturbed_gradient.r624.value | 0.31086038695472196 | 318975 | eV A^-1 |
| P.xtb_perturbed_gradient.r623.value | 0.037600367399297924 | 2000 | Eh |
| P.xtb_perturbed_gradient.r625.value | 0.0059074682043337035 | 318975 | Eh bohr^-1 |
